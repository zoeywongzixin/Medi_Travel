import os
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/medical_matching")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    status = Column(String)
    condition = Column(String)
    hospital = Column(String)
    flight = Column(String)
    charity = Column(String)
    urgency = Column(String)
    feedback = Column(Text)

class Selection(Base):
    __tablename__ = "selections"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    doctor_id = Column(String)
    charity_id = Column(String)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def log_match(session_id: str, status: str, condition: str, hospital: str, flight: str, charity: str, urgency: str) -> int:
    db = SessionLocal()
    new_match = Match(
        session_id=session_id,
        status=status,
        condition=condition,
        hospital=hospital,
        flight=flight,
        charity=charity,
        urgency=urgency,
        feedback=""
    )
    db.add(new_match)
    db.commit()
    db.refresh(new_match)
    db.close()
    return new_match.id

def update_feedback(match_id: int, feedback: str, new_status: str = "edited"):
    db = SessionLocal()
    match = db.query(Match).filter(Match.id == match_id).first()
    if match:
        match.feedback = feedback
        match.status = new_status
        db.commit()
    db.close()

def get_few_shot_feedback(condition: str):
    db = SessionLocal()
    matches = db.query(Match).filter(
        Match.status == 'edited',
        Match.feedback != '',
        Match.condition.ilike(f"%{condition}%")
    ).limit(5).all()
    results = [{"condition": m.condition, "feedback": m.feedback} for m in matches]
    db.close()
    return results

# Initialize on import
init_db()
