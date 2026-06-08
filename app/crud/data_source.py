from typing import Optional

from sqlalchemy.orm import Session

from app.models.data_source import DataSource
from app.schemas.data_source import DataSourceCreate, DataSourceUpdate


def create_data_source(db: Session, data: DataSourceCreate) -> DataSource:
    data_source = DataSource(
        name=data.name,
        db_type=data.db_type,
        host=data.host,
        port=data.port,
        username=data.username,
        password=data.password,
        database_name=data.database_name,
        description=data.description,
    )
    db.add(data_source)
    db.commit()
    db.refresh(data_source)
    return data_source


def get_data_source(db: Session, data_source_id: str) -> Optional[DataSource]:
    return db.query(DataSource).filter(DataSource.id == data_source_id).first()


def list_data_sources(db: Session, skip: int = 0, limit: int = 10) -> tuple[list[DataSource], int]:
    total = db.query(DataSource).count()
    data_sources = db.query(DataSource).offset(skip).limit(limit).all()
    return data_sources, total


def update_data_source(db: Session, data_source_id: str, data: DataSourceUpdate) -> Optional[DataSource]:
    data_source = get_data_source(db, data_source_id)
    if data_source:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(data_source, field, value)
        db.commit()
        db.refresh(data_source)
    return data_source


def delete_data_source(db: Session, data_source_id: str) -> bool:
    data_source = get_data_source(db, data_source_id)
    if data_source:
        db.delete(data_source)
        db.commit()
        return True
    return False
