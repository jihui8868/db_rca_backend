from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentResponse, DepartmentUpdate

router = APIRouter(prefix="/departments", tags=["departments"])


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(dept: DepartmentCreate, db: Session = Depends(get_db)):
    existing_dept = db.query(Department).filter(Department.name == dept.name).first()
    if existing_dept:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department name already exists"
        )
    new_dept = Department(name=dept.name, description=dept.description)
    db.add(new_dept)
    db.commit()
    db.refresh(new_dept)
    return new_dept


@router.get("/{dept_id}", response_model=DepartmentResponse)
def get_department(dept_id: str, db: Session = Depends(get_db)):
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    return dept


@router.get("", response_model=list[DepartmentResponse])
def list_departments(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    depts = db.query(Department).offset(skip).limit(limit).all()
    return depts


@router.put("/{dept_id}", response_model=DepartmentResponse)
def update_department(dept_id: str, dept_update: DepartmentUpdate, db: Session = Depends(get_db)):
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    update_data = dept_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(dept, field, value)
    db.commit()
    db.refresh(dept)
    return dept


@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(dept_id: str, db: Session = Depends(get_db)):
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    db.delete(dept)
    db.commit()
