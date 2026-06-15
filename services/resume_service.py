"""CRUD operations for resumes and tailored resumes."""
from contextlib import contextmanager

from sqlalchemy.orm import Session

from db.engine import SessionLocal
from db.models import Resume, TailoredResume


@contextmanager
def _session() -> Session:
    """Yield a database session, ensuring it's closed afterwards."""
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


# ── Resume CRUD ────────────────────────────────────────────────────────────


def list_resumes() -> list[Resume]:
    """Return all saved base resumes, newest first."""
    with _session() as s:
        return s.query(Resume).order_by(Resume.updated_at.desc()).all()


def get_resume(resume_id: int) -> Resume | None:
    """Get a single resume by ID."""
    with _session() as s:
        return s.get(Resume, resume_id)


def create_resume(name: str, content: str, notes: str = "") -> Resume:
    """Create a new base resume."""
    with _session() as s:
        r = Resume(name=name.strip(), content=content, notes=notes)
        s.add(r)
        s.commit()
        s.refresh(r)
        return r


def update_resume(resume_id: int, name: str, content: str, notes: str) -> Resume | None:
    """Update an existing resume. Returns None if not found."""
    with _session() as s:
        r = s.get(Resume, resume_id)
        if r is None:
            return None
        r.name = name.strip()
        r.content = content
        r.notes = notes
        s.commit()
        s.refresh(r)
        return r


def delete_resume(resume_id: int) -> bool:
    """Delete a resume by ID. Returns True if deleted, False if not found."""
    with _session() as s:
        r = s.get(Resume, resume_id)
        if r is None:
            return False
        s.delete(r)
        s.commit()
        return True


# ── Tailored Resume CRUD ───────────────────────────────────────────────────


def save_tailored_resume(
    source_resume_id: int,
    job_description: str,
    tailored_text: str,
    company_hint: str = "",
    role_hint: str = "",
) -> TailoredResume:
    """Persist a tailored resume to history."""
    with _session() as s:
        tr = TailoredResume(
            source_resume_id=source_resume_id,
            job_description=job_description,
            tailored_text=tailored_text,
            company_hint=company_hint,
            role_hint=role_hint,
        )
        s.add(tr)
        s.commit()
        s.refresh(tr)
        return tr


def list_tailored_resumes() -> list[TailoredResume]:
    """Return all tailored resumes, newest first."""
    with _session() as s:
        return (
            s.query(TailoredResume)
            .order_by(TailoredResume.created_at.desc())
            .all()
        )


def get_tailored_resume(tailored_id: int) -> TailoredResume | None:
    """Get a single tailored resume by ID."""
    with _session() as s:
        return s.get(TailoredResume, tailored_id)


def delete_tailored_resume(tailored_id: int) -> bool:
    """Delete a tailored resume from history."""
    with _session() as s:
        tr = s.get(TailoredResume, tailored_id)
        if tr is None:
            return False
        s.delete(tr)
        s.commit()
        return True
