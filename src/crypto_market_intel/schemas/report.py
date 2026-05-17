from pydantic import BaseModel


class DailyReport(BaseModel):
    report_date: str
    title: str
    content_markdown: str

class AlertReport(BaseModel):
    report_date: str
    title: str
    content_markdown: str
