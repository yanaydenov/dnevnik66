import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import httpx
from config import DNEVNIK_API_URL

logger = logging.getLogger(__name__)


class DnevnikHttpError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class DnevnikUnauthorizedError(DnevnikHttpError):
    pass


class DnevnikExternalServerError(DnevnikHttpError):
    pass


class DnevnikClient:
    def __init__(self, access_token: str, refresh_token: str, base_url: str = DNEVNIK_API_URL):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.base_url = base_url
        self.student_id: Optional[str] = None
        self.class_id: Optional[str] = None
        self.school_year: Optional[str] = None
        self.periods_ids: List[str] = []
        self._cached_profile: Optional[Dict[str, Any]] = None

    def _headers(self) -> Dict[str, str]:
        return {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }

    async def _request(self, method: str, path: str, json_body: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=25.0) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self._headers(),
                    json=json_body,
                    params=params,
                )
            except httpx.RequestError as e:
                logger.error(f"Network error requesting {url}: {e}")
                raise DnevnikExternalServerError(f"Network error: {e}")

            if response.status_code == 200:
                try:
                    return response.json()
                except Exception:
                    return response.text

            logger.warning(f"Dnevnik API returned {response.status_code} for {path}")

            if response.status_code in (400, 401, 403):
                raise DnevnikUnauthorizedError(f"Unauthorized ({response.status_code}): {response.text}", response.status_code)
            elif response.status_code in (500, 502, 503, 504):
                raise DnevnikExternalServerError(f"Server error ({response.status_code}): {response.text}", response.status_code)
            else:
                raise DnevnikHttpError(f"HTTP {response.status_code}: {response.text}", response.status_code)

    async def refresh_tokens(self) -> Tuple[str, str]:
        """Refreshes tokens and updates client state"""
        if not self.refresh_token:
            raise DnevnikUnauthorizedError("No refresh token provided")

        body = {"refreshToken": self.refresh_token}
        data = await self._request("POST", "/auth/Token/Refresh", json_body=body)
        if isinstance(data, dict) and "accessToken" in data and "refreshToken" in data:
            self.access_token = data["accessToken"]
            self.refresh_token = data["refreshToken"]
            return self.access_token, self.refresh_token
        raise DnevnikUnauthorizedError(f"Invalid refresh response: {data}")

    async def init_ids(self) -> None:
        """Initializes studentId, classId, schoolYear, and periodsIds"""
        if self.student_id and self.class_id and self.periods_ids:
            return

        students_data = await self.get_students()
        students = students_data.get("students", [])
        if not students:
            raise DnevnikHttpError("No students found in account")

        # Select first student or already selected
        student = students[0]
        self.student_id = student["id"]
        self._cached_profile = student

        # Get school year
        years_res = await self._request("GET", "/estimate/years", params={"studentId": self.student_id})
        self.school_year = years_res.get("currentYear", {}).get("id", str(datetime.now().year))

        # Get class ID
        classes_res = await self._request("GET", "/classes", params={"studentId": self.student_id, "schoolYear": self.school_year})
        self.class_id = classes_res.get("currentClass", {}).get("value", "")

        # Get periods IDs
        periods_res = await self._request("GET", "/estimate/periods", params={"studentId": self.student_id, "schoolYear": self.school_year})
        periods = periods_res.get("periods", [])
        self.periods_ids = [p["id"] for p in periods]

    async def profile(self) -> Dict[str, Any]:
        """Returns student profile dictionary"""
        if self._cached_profile:
            return self._cached_profile
        students_data = await self.get_students()
        students = students_data.get("students", [])
        if students:
            self._cached_profile = students[0]
            self.student_id = students[0]["id"]
            return students[0]
        return {}

    async def get_students(self) -> Dict[str, Any]:
        return await self._request("GET", "/students")

    async def schedule(self, day_idx: int, date_str: Optional[str] = None) -> List[Dict[str, str]]:
        """Returns list of lessons for the given day index (0=Monday..5=Saturday)"""
        await self.init_ids()
        params = {"studentId": self.student_id}
        if date_str:
            params["date"] = date_str

        data = await self._request("GET", "/schedule", params=params)
        days = data.get("scheduleModel", {}).get("days", [])

        if day_idx < len(days):
            target_day = days[day_idx]
            lesson_models = target_day.get("scheduleDayLessonModels", [])
            result = []
            for num, l in enumerate(lesson_models, 1):
                result.append({
                    "num": str(l.get("number", num)),
                    "name": l.get("lessonName", ""),
                    "room": l.get("room", "") or "",
                    "beginHour": l.get("beginHour"),
                    "beginMinute": l.get("beginMinute"),
                    "endHour": l.get("endHour"),
                    "endMinute": l.get("endMinute"),
                })
            return result
        return []

    async def schedule_raw(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        await self.init_ids()
        params = {"studentId": self.student_id}
        if date_str:
            params["date"] = date_str
        return await self._request("GET", "/schedule", params=params)

    async def homework(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """Returns homework data for a date with pagination links"""
        await self.init_ids()
        params = {"studentId": self.student_id}
        if date_str:
            params["date"] = date_str

        hw = await self._request("GET", "/homework", params=params)
        result = {
            "date": hw.get("date", datetime.now().strftime("%Y-%m-%d")),
            "pages": hw.get("pagination", {}),
            "homework": []
        }
        for item in hw.get("homeworks", []):
            files = item.get("homeWorkFiles", [])
            result["homework"].append({
                "lessonName": item.get("lessonName", ""),
                "description": item.get("description", "") or "Нет задания",
                "filesCount": len(files),
                "files": files,
                "isDone": item.get("isDone", False),
            })
        return result

    async def grades_week(self) -> Dict[str, List[List[Any]]]:
        """Returns dict of discipline -> list of grade arrays for the current week"""
        await self.init_ids()
        if not self.periods_ids:
            return {}

        period_id = self.periods_ids[0]
        data = await self._request("GET", "/estimate", params={
            "schoolYear": self.school_year,
            "classId": self.class_id,
            "periodId": period_id,
            "subjectId": "00000000-0000-0000-0000-000000000000",
            "studentId": self.student_id,
        })

        res: Dict[str, List[List[Any]]] = {}
        for day in data.get("weekGradesTable", {}).get("days", []):
            for item in day.get("lessonGrades", []):
                name = item.get("name", "")
                grades = item.get("grades", [])
                if name in res:
                    res[name].extend(grades)
                else:
                    res[name] = list(grades)
        return res

    async def grades_period(self, period_idx: int) -> List[Dict[str, Any]]:
        """Returns grades list for a quarter/period (0=1st quarter, 1=2nd quarter, ...)"""
        await self.init_ids()
        # Period index offset: periods_ids[0] is current week, [1] is year, [2..5] are quarters 1..4
        target_period_id = self.periods_ids[period_idx + 2] if (period_idx + 2) < len(self.periods_ids) else self.periods_ids[-1]

        data = await self._request("GET", "/estimate", params={
            "schoolYear": self.school_year,
            "classId": self.class_id,
            "periodId": target_period_id,
            "subjectId": "00000000-0000-0000-0000-000000000000",
            "studentId": self.student_id,
        })

        res = []
        for disc in data.get("periodGradesTable", {}).get("disciplines", []):
            all_grades = []
            for grp in disc.get("grades", []):
                for g in grp.get("grades", []):
                    all_grades.append(g)
            res.append({
                "name": disc.get("name", ""),
                "average": disc.get("averageGrade", 0.0),
                "averagew": disc.get("averageWeightedGrade", 0.0),
                "grades": all_grades,
            })
        return res

    async def grades_year(self) -> List[Dict[str, Any]]:
        """Returns year grades per subject with 4 quarter grades and final mark"""
        await self.init_ids()
        if len(self.periods_ids) < 2:
            return []

        year_period_id = self.periods_ids[1]
        data = await self._request("GET", "/estimate", params={
            "schoolYear": self.school_year,
            "classId": self.class_id,
            "periodId": year_period_id,
            "subjectId": "00000000-0000-0000-0000-000000000000",
            "studentId": self.student_id,
        })

        res = []
        for item in data.get("yearGradesTable", {}).get("lessonGrades", []):
            lesson_name = item.get("lesson", {}).get("name", item.get("name", ""))
            quarter_grades = []
            for g in item.get("grades", []):
                quarter_grades.append(g.get("finallygrade") or "━")

            # Pad to 4 quarters if less
            while len(quarter_grades) < 4:
                quarter_grades.append("━")

            res.append({
                "name": lesson_name,
                "grades": quarter_grades[:4],
                "yeargrade": item.get("yearGrade") or item.get("finallyGrade") or "━",
            })
        return res
