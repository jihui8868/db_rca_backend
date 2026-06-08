from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import data_source as crud_data_source
from app.schemas.data_source import (
    DataSourceCreate,
    DataSourceListResponse,
    DataSourceResponse,
    DataSourceUpdate,
)

router = APIRouter(prefix="/data-sources", tags=["data-sources"])


@router.post("", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
def create_data_source(data: DataSourceCreate, db: Session = Depends(get_db)):
    return crud_data_source.create_data_source(db, data)


@router.get("/{data_source_id}", response_model=DataSourceResponse)
def get_data_source(data_source_id: str, db: Session = Depends(get_db)):
    data_source = crud_data_source.get_data_source(db, data_source_id)
    if not data_source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found"
        )
    return data_source


@router.get("", response_model=DataSourceListResponse)
def list_data_sources(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    data_sources, total = crud_data_source.list_data_sources(db, skip, limit)
    return DataSourceListResponse(data_sources=data_sources, total=total)


@router.put("/{data_source_id}", response_model=DataSourceResponse)
def update_data_source(data_source_id: str, data: DataSourceUpdate, db: Session = Depends(get_db)):
    data_source = crud_data_source.update_data_source(db, data_source_id, data)
    if not data_source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found"
        )
    return data_source


@router.delete("/{data_source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_data_source(data_source_id: str, db: Session = Depends(get_db)):
    success = crud_data_source.delete_data_source(db, data_source_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found"
        )
