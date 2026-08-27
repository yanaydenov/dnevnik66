import asyncio
import logging
from typing import Optional, Dict, Any, List, Tuple, Callable
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
    def __init__(
        self,
        access_token: str,
        refresh_token: str,
        base_url: str = DNEVNIK_API_URL,
        on_token_refreshed: Optional[Callable[[str, str], Any]] = None,
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.base_url = base_url
        self.on_token_refreshed = on_token_refreshed
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

    async def _request(
        self,
        method: str,
        path: str,
        json_body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        retry_on_401: bool = True,
    ) -> Any:
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

            # Handle 401 token expiration with auto-refresh
            if response.status_code == 401 and retry_on_401 and path != "/auth/Token/Refresh" and self.refresh_token:
                logger.info(f"Got 401 for {path}, attempting auto token refresh...")
                try:
                    await self.refresh_tokens()
                    # Retry request with new token
                    return await self._request(method, path, json_body, params, retry_on_401=False)
                except Exception as refresh_err:
                    logger.warning(f"Auto-refresh failed after 401: {refresh_err}")
                    raise DnevnikUnauthorizedError("Сессия истекла, требуется повторный вход (/login)", 401)

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
        data = await self._request("POST", "/auth/Token/Refresh", json_body=body, retry_on_401=False)
        if isinstance(data, dict) and "accessToken" in data and "refreshToken" in data:
            self.access_token = data["accessToken"]
            self.refresh_token = data["refreshToken"]

            if self.on_token_refreshed:
                try:
                    res = self.on_token_refreshed(self.access_token, self.refresh_token)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as e:
                    logger.error(f"Error in on_token_refreshed callback: {e}")

            return self.access_token, self.refresh_token
        raise DnevnikUnauthorizedError(f"Invalid refresh response: {data}")

    async def init_student_id(self) -> None:
        """Initializes studentId and profile without needing class/periods"""
        if self.student_id:
            return

        students_data = await self.get_students()
        students = students_data.get("students", []) if isinstance(students_data, dict) else []
        if not students:
            raise DnevnikHttpError("No students found in account")

        student = students[0]
        self.student_id = student["id"]
        self._cached_profile = student

    async def init_ids(self) -> None:
        """Initializes studentId, classId, schoolYear, and periodsIds with fallback support"""
        await self.init_student_id()

        if self.class_id and self.periods_ids and self.school_year:
            return

        # 1. Fetch available school years
        candidate_years: List[str] = []
        try:
            years_res = await self._request("GET", "/estimate/years", params={"studentId": self.student_id})
            if isinstance(years_res, dict):
                curr = years_res.get("currentYear")
                if isinstance(curr, dict) and curr.get("id"):
                    candidate_years.append(str(curr["id"]))
                elif isinstance(curr, (str, int)):
                    candidate_years.append(str(curr))

                for y in years_res.get("years", []):
                    if isinstance(y, dict) and y.get("id"):
                        y_id = str(y["id"])
                        if y_id not in candidate_years:
                            candidate_years.append(y_id)
        except Exception as e:
            logger.warning(f"Could not fetch years from /estimate/years: {e}")

        if not candidate_years:
            curr_year = datetime.now().year
            candidate_years = [str(curr_year), str(curr_year - 1)]

        last_error = None
        for yr in candidate_years:
            try:
                # 2. Get class ID for this year
                classes_res = await self._request("GET", "/classes", params={"studentId": self.student_id, "schoolYear": yr})
                class_id = ""
                if isinstance(classes_res, dict):
                    curr_cls = classes_res.get("currentClass")
                    if isinstance(curr_cls, dict):
                        class_id = str(curr_cls.get("value") or curr_cls.get("id") or "")
                    elif isinstance(curr_cls, str):
                        class_id = curr_cls

                    if not class_id:
                        classes_list = classes_res.get("classes", [])
                        if classes_list and isinstance(classes_list[0], dict):
                            class_id = str(classes_list[0].get("value") or classes_list[0].get("id") or "")

                if not class_id:
                    continue

                # 3. Get periods IDs for this year and class (MUST pass classId)
                periods_res = await self._request("GET", "/estimate/periods", params={
                    "studentId": self.student_id,
                    "schoolYear": yr,
                    "classId": class_id,
                })

                periods = periods_res.get("periods", []) if isinstance(periods_res, dict) else []
                if periods:
                    self.school_year = yr
                    self.class_id = class_id
                    self.periods_ids = [p["id"] for p in periods if isinstance(p, dict) and "id" in p]
                    logger.info(f"Initialized grades context: year={yr}, classId={class_id}, periods count={len(self.periods_ids)}")
                    return
            except Exception as e:
                last_error = e
                logger.warning(f"Failed to init periods for schoolYear={yr}: {e}")
                continue

        if last_error:
            raise last_error
        raise DnevnikHttpError("Не удалось определить учебный период или класс ученика")

    async def profile(self) -> Dict[str, Any]:
        """Returns student profile dictionary"""
        if self._cached_profile:
            return self._cached_profile
        students_data = await self.get_students()
        students = students_data.get("students", []) if isinstance(students_data, dict) else []
        if students:
            self._cached_profile = students[0]
            self.student_id = students[0]["id"]
            return students[0]
        return {}

    async def get_students(self) -> Dict[str, Any]:
        return await self._request("GET", "/students")

    async def schedule(self, day_idx: int, date_str: Optional[str] = None) -> List[Dict[str, str]]:
        """Returns list of lessons for the given day index (0=Monday..5=Saturday)"""
        await self.init_student_id()
        params = {"studentId": self.student_id}
        if date_str:
            params["date"] = date_str

        data = await self._request("GET", "/schedule", params=params)
        if not isinstance(data, dict):
            return []

        schedule_model = data.get("scheduleModel") or {}
        days = schedule_model.get("days") or []

        if day_idx < len(days):
            target_day = days[day_idx] or {}
            lesson_models = target_day.get("scheduleDayLessonModels") or []
            result = []
            for num, l in enumerate(lesson_models, 1):
                if not isinstance(l, dict):
                    continue
                result.append({
                    "num": str(l.get("number") or num),
                    "name": l.get("lessonName") or "",
                    "room": l.get("room") or "",
                    "beginHour": l.get("beginHour"),
                    "beginMinute": l.get("beginMinute"),
                    "endHour": l.get("endHour"),
                    "endMinute": l.get("endMinute"),
                })
            return result
        return []

    async def schedule_raw(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        await self.init_student_id()
        params = {"studentId": self.student_id}
        if date_str:
            params["date"] = date_str
        res = await self._request("GET", "/schedule", params=params)
        return res if isinstance(res, dict) else {}

    async def homework(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """Returns homework data for a date with pagination links"""
        await self.init_student_id()
        params = {"studentId": self.student_id}
        if date_str:
            params["date"] = date_str

        hw = await self._request("GET", "/homework", params=params)
        if not isinstance(hw, dict):
            hw = {}

        result = {
            "date": hw.get("date") or datetime.now().strftime("%Y-%m-%d"),
            "pages": hw.get("pagination") or {},
            "homework": []
        }
        for item in (hw.get("homeworks") or []):
            if not isinstance(item, dict):
                continue
            files = item.get("homeWorkFiles") or []
            result["homework"].append({
                "lessonName": item.get("lessonName") or "",
                "description": item.get("description") or "Нет задания",
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

        if not isinstance(data, dict):
            return {}

        week_table = data.get("weekGradesTable") or {}
        days = week_table.get("days") or []
        res: Dict[str, List[List[Any]]] = {}
        for day in days:
            if not isinstance(day, dict):
                continue
            for item in (day.get("lessonGrades") or []):
                if not isinstance(item, dict):
                    continue
                name = item.get("name") or ""
                grades = item.get("grades") or []
                if name in res:
                    res[name].extend(grades)
                else:
                    res[name] = list(grades)
        return res

    async def grades_period(self, period_idx: int) -> List[Dict[str, Any]]:
        """Returns grades list for a quarter/period (0=1st quarter, 1=2nd quarter, ...)"""
        await self.init_ids()
        if len(self.periods_ids) >= 6:
            target_period_id = self.periods_ids[period_idx + 2] if (period_idx + 2) < len(self.periods_ids) else self.periods_ids[-1]
        elif len(self.periods_ids) > 0:
            target_period_id = self.periods_ids[period_idx] if period_idx < len(self.periods_ids) else self.periods_ids[-1]
        else:
            return []

        data = await self._request("GET", "/estimate", params={
            "schoolYear": self.school_year,
            "classId": self.class_id,
            "periodId": target_period_id,
            "subjectId": "00000000-0000-0000-0000-000000000000",
            "studentId": self.student_id,
        })

        if not isinstance(data, dict):
            return []

        period_table = data.get("periodGradesTable") or {}
        disciplines = period_table.get("disciplines") or []
        res = []
        for disc in disciplines:
            if not isinstance(disc, dict):
                continue
            all_grades = []
            for grp in (disc.get("grades") or []):
                if isinstance(grp, dict):
                    for g in (grp.get("grades") or []):
                        all_grades.append(g)
                elif isinstance(grp, list):
                    all_grades.extend(grp)
                elif grp is not None:
                    all_grades.append(grp)

            res.append({
                "name": disc.get("name") or "",
                "average": disc.get("averageGrade") or 0.0,
                "averagew": disc.get("averageWeightedGrade") or 0.0,
                "grades": all_grades,
            })
        return res

    async def grades_year(self) -> List[Dict[str, Any]]:
        """Returns year grades per subject with 4 quarter grades and final mark"""
        await self.init_ids()
        if len(self.periods_ids) < 2:
            return []

        year_period_id = self.periods_ids[1] if len(self.periods_ids) >= 2 else self.periods_ids[0]
        data = await self._request("GET", "/estimate", params={
            "schoolYear": self.school_year,
            "classId": self.class_id,
            "periodId": year_period_id,
            "subjectId": "00000000-0000-0000-0000-000000000000",
            "studentId": self.student_id,
        })

        if not isinstance(data, dict):
            return []

        year_table = data.get("yearGradesTable") or {}
        lesson_grades = year_table.get("lessonGrades") or []
        res = []
        for item in lesson_grades:
            if not isinstance(item, dict):
                continue
            lesson = item.get("lesson") or {}
            lesson_name = lesson.get("name") if isinstance(lesson, dict) else item.get("name") or ""
            quarter_grades = []
            for g in (item.get("grades") or []):
                if isinstance(g, dict):
                    quarter_grades.append(g.get("finallygrade") or g.get("finallyGrade") or "━")
                elif g is not None:
                    quarter_grades.append(str(g))

            # Pad to 4 quarters if less
            while len(quarter_grades) < 4:
                quarter_grades.append("━")

            year_grade = item.get("yearGrade") or item.get("finallyGrade") or item.get("finallygrade") or "━"
            res.append({
                "name": lesson_name,
                "grades": quarter_grades[:4],
                "yeargrade": year_grade,
            })
        return res
