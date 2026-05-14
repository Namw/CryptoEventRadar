from pydantic import BaseModel


class DailyReport(BaseModel):
    report_date: str
    title: str
    content_markdown: str
