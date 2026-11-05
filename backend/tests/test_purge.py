"""Demo clean-up for real deployments: purge the demo school and accounts, then create the first administrator."""
import tempfile

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models import Assessment, School, Student, Submission, User
from app.seed import seed_demo
from app.seed.purge import create_admin, purge_demo


def test_purge_removes_all_demo_data_and_keeps_real_data():
    engine = create_engine(f"sqlite:///{tempfile.mkdtemp()}/purge.db")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    seed_demo(db)
    real = School(name="Нақты мектеп")
    db.add(real)
    db.flush()
    db.add(User(email="real@school.kz", full_name="Нақты", role="teacher", school_id=real.id, password_hash="x"))
    db.commit()
    assert db.scalar(select(func.count(Submission.id))) > 0

    out = purge_demo(db)
    assert out["schools"] == 1 and out["users"] == 5
    assert [s.name for s in db.scalars(select(School))] == ["Нақты мектеп"]
    for model in (Assessment, Student, Submission):
        assert db.scalar(select(func.count(model.id))) == 0
    assert [u.email for u in db.scalars(select(User))] == ["real@school.kz"]

    pw = create_admin(db, "Boss@School.kz")
    assert pw and db.scalar(select(User).where(User.role == "admin")).email == "boss@school.kz"
    assert create_admin(db, "other@school.kz") is None
    assert purge_demo(db)["schools"] == 0
