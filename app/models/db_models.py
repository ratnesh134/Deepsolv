from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Text

class Base(DeclarativeBase):
    pass

class BrandSnapshot(Base):
    __tablename__ = "brand_snapshot"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    website_url: Mapped[str] = mapped_column(String(512), index=True, unique=False)
    brand_name: Mapped[str] = mapped_column(String(256), nullable=True)
    json_payload: Mapped[str] = mapped_column(Text)  # store full JSON as text
