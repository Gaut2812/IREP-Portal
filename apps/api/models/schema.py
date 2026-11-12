import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Float, Boolean, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import TenantModel

class College(TenantModel):
    __tablename__ = "colleges"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

class User(TenantModel):
    __tablename__ = "users"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), index=True, nullable=False) # student, trainer, college_admin, parent, super_admin
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    avatar_initials: Mapped[str] = mapped_column(String(8), default="IR")
    language_pref: Mapped[str] = mapped_column(String(8), default="en") # en or ta
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class Student(TenantModel):
    __tablename__ = "students"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"))
    register_no: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    branch: Mapped[str] = mapped_column(String(64), default="AI & DS")
    semester: Mapped[int] = mapped_column(Integer, default=5)
    batch_name: Mapped[str] = mapped_column(String(64), default="AI & DS · Sem 5 Batch")
    readiness_score: Mapped[int] = mapped_column(Integer, default=74)
    readiness_band: Mapped[str] = mapped_column(String(32), default="Nearly Ready") # Placement Ready, Nearly Ready, Needs Support
    readiness_delta: Mapped[int] = mapped_column(Integer, default=6)
    problems_solved: Mapped[int] = mapped_column(Integer, default=286)
    attendance_pct: Mapped[int] = mapped_column(Integer, default=92)
    streak_days: Mapped[int] = mapped_column(Integer, default=19)

class Trainer(TenantModel):
    __tablename__ = "trainers"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"))
    designation: Mapped[str] = mapped_column(String(128), default="Senior Technical Trainer")
    specialization: Mapped[str] = mapped_column(String(128), default="AI & Cloud Systems")

class ParentStudent(TenantModel):
    __tablename__ = "parent_student"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    parent_user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"))
    student_id: Mapped[str] = mapped_column(String(64), ForeignKey("students.id"))
    relationship: Mapped[str] = mapped_column(String(32), default="Father")

# Screen 08 & 13: Live Sessions and Attendance
class SessionItem(TenantModel):
    __tablename__ = "sessions"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    track: Mapped[str] = mapped_column(String(64), default="AI & DS")
    trainer_name: Mapped[str] = mapped_column(String(128), default="Arun Kumar")
    scheduled_start: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    scheduled_end: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, default=60)
    session_type: Mapped[str] = mapped_column(String(32), default="Live") # Live, In-lab / Hybrid
    status: Mapped[str] = mapped_column(String(32), default="Upcoming") # Attended, Missed, Upcoming, Scheduled, In Progress
    recording_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    recording_duration: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    has_lab_preload: Mapped[bool] = mapped_column(Boolean, default=False)
    lab_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

class SessionAttendance(TenantModel):
    __tablename__ = "session_attendance"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("sessions.id"))
    student_id: Mapped[str] = mapped_column(String(64), ForeignKey("students.id"))
    minutes_present: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="Present") # Present, Absent, Partial
    marked_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

# Screen 24: Coding Lab
class CodingProblem(TenantModel):
    __tablename__ = "coding_problems"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(32), default="Medium")
    topic: Mapped[str] = mapped_column(String(64), default="Union-Find")
    company_tags: Mapped[str] = mapped_column(String(255), default="Product cos.")
    week_info: Mapped[str] = mapped_column(String(128), default="Week 8 · Pattern drill · 3 of 6 solved")
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    example_input: Mapped[str] = mapped_column(Text)
    example_output: Mapped[str] = mapped_column(Text)
    constraints: Mapped[str] = mapped_column(Text)
    starter_code: Mapped[str] = mapped_column(Text)
    trainer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trainer_author: Mapped[str] = mapped_column(String(128), default="Arun K.")

class CodingSubmission(TenantModel):
    __tablename__ = "coding_submissions"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    problem_id: Mapped[str] = mapped_column(String(64), ForeignKey("coding_problems.id"))
    student_id: Mapped[str] = mapped_column(String(64), ForeignKey("students.id"))
    language: Mapped[str] = mapped_column(String(32), default="python")
    code: Mapped[str] = mapped_column(Text, nullable=False)
    runtime_ms: Mapped[int] = mapped_column(Integer, default=42)
    memory_mb: Mapped[float] = mapped_column(Float, default=16.1)
    status: Mapped[str] = mapped_column(String(32), default="Passed")
    tests_passed: Mapped[int] = mapped_column(Integer, default=18)
    tests_total: Mapped[int] = mapped_column(Integer, default=18)
    hints_used: Mapped[int] = mapped_column(Integer, default=1)

# Screen 23: Practice Tests
class PracticeTest(TenantModel):
    __tablename__ = "practice_tests"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(128), default="Service Company Pattern · Aptitude")
    duration_min: Mapped[int] = mapped_column(Integer, default=30)
    total_questions: Mapped[int] = mapped_column(Integer, default=30)
    sections_json: Mapped[dict] = mapped_column(JSON, default=dict)

class PracticeQuestion(TenantModel):
    __tablename__ = "practice_questions"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    test_id: Mapped[str] = mapped_column(String(64), ForeignKey("practice_tests.id"))
    question_number: Mapped[int] = mapped_column(Integer, nullable=False)
    section_name: Mapped[str] = mapped_column(String(64), default="Quantitative")
    topic: Mapped[str] = mapped_column(String(64), default="Time & Work")
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    option_a: Mapped[str] = mapped_column(String(255))
    option_b: Mapped[str] = mapped_column(String(255))
    option_c: Mapped[str] = mapped_column(String(255))
    option_d: Mapped[str] = mapped_column(String(255))
    correct_option: Mapped[str] = mapped_column(String(8), default="B")
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

class TestAttempt(TenantModel):
    __tablename__ = "test_attempts"
    __test__ = False

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    test_id: Mapped[str] = mapped_column(String(64), ForeignKey("practice_tests.id"), index=True)
    student_id: Mapped[str] = mapped_column(String(64), ForeignKey("students.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="in_progress") # in_progress, submitted, expired
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    ends_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    submitted_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_questions: Mapped[int] = mapped_column(Integer, default=30)
    accuracy_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    time_taken_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

class AttemptAnswer(TenantModel):
    __tablename__ = "attempt_answers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(String(64), ForeignKey("test_attempts.id"), index=True)
    question_id: Mapped[str] = mapped_column(String(64), ForeignKey("practice_questions.id"))
    question_number: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_option: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    is_marked_for_review: Mapped[bool] = mapped_column(Boolean, default=False)
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    saved_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

class ProctorEvent(TenantModel):
    __tablename__ = "proctor_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(String(64), ForeignKey("test_attempts.id"), index=True)
    student_id: Mapped[str] = mapped_column(String(64), ForeignKey("students.id"))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False) # tab_switch, fullscreen_exit, copy_paste_attempt
    details: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

class TopicScore(TenantModel):
    __tablename__ = "topic_scores"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(String(64), ForeignKey("test_attempts.id"), index=True)
    section_name: Mapped[str] = mapped_column(String(64), nullable=False)
    topic: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    accuracy_pct: Mapped[float] = mapped_column(Float, default=0.0)
    status_band: Mapped[str] = mapped_column(String(32), default="Good") # Strong, Good, Needs Support

# Screen 29: Virtual Labs
class VirtualLabItem(TenantModel):
    __tablename__ = "virtual_labs"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="Software Engineering")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    eligibility_chip: Mapped[str] = mapped_column(String(64), default="Sem 2+")
    status_chip: Mapped[str] = mapped_column(String(64), default="Ready")
    tag_color: Mapped[str] = mapped_column(String(32), default="green")
    footer_text: Mapped[str] = mapped_column(String(128))
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active_session: Mapped[bool] = mapped_column(Boolean, default=False)
    active_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    active_minutes: Mapped[int] = mapped_column(Integer, default=0)

# Screen 30: Sprint Board
class SprintTask(TenantModel):
    __tablename__ = "sprint_tasks"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), default="proj_clinic_01")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    tag: Mapped[str] = mapped_column(String(64), default="Feature")
    tag_type: Mapped[str] = mapped_column(String(32), default="feature") # feature, ai, backend, frontend, qa, devops
    column_name: Mapped[str] = mapped_column(String(32), default="todo") # todo, in_progress, code_review, done
    assignee_initials: Mapped[str] = mapped_column(String(8), default="PR")
    assignee_name: Mapped[str] = mapped_column(String(64), default="Priya R")
    story_points: Mapped[int] = mapped_column(Integer, default=3)
    pr_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

# Screen 36: Mock Interviews
class MockInterview(TenantModel):
    __tablename__ = "mock_interviews"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(64), ForeignKey("students.id"))
    round_title: Mapped[str] = mapped_column(String(128), default="Mock Interview #2 – Technical")
    interview_date: Mapped[str] = mapped_column(String(64), default="Oct 8 · 40 min")
    interviewer_name: Mapped[str] = mapped_column(String(128), default="Arun K.")
    overall_score: Mapped[float] = mapped_column(Float, default=3.8)
    service_chip: Mapped[str] = mapped_column(String(64), default="Hire-ready for service roles")
    product_chip: Mapped[str] = mapped_column(String(64), default="Improve for product roles")
    problem_solving: Mapped[int] = mapped_column(Integer, default=4)
    coding_correctness: Mapped[int] = mapped_column(Integer, default=4)
    thinking_aloud: Mapped[int] = mapped_column(Integer, default=3)
    core_cs: Mapped[int] = mapped_column(Integer, default=4)
    project_explanation: Mapped[int] = mapped_column(Integer, default=4)
    communication: Mapped[int] = mapped_column(Integer, default=3)
    feedback_text: Mapped[str] = mapped_column(Text)
    recording_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

# Screen 34 & 35: Discussion Groups & Trainer Message Hub
class DiscussionGroup(TenantModel):
    __tablename__ = "discussion_groups"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    unread_badge: Mapped[int] = mapped_column(Integer, default=0)
    is_locked_announcement: Mapped[bool] = mapped_column(Boolean, default=False)
    moderators: Mapped[str] = mapped_column(String(255), default="Arun K. and Meena S.")
    members_count: Mapped[int] = mapped_column(Integer, default=42)
    online_count: Mapped[int] = mapped_column(Integer, default=18)
    pinned_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

class GroupMessage(TenantModel):
    __tablename__ = "group_messages"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    group_id: Mapped[str] = mapped_column(String(64), ForeignKey("discussion_groups.id"))
    sender_name: Mapped[str] = mapped_column(String(128), nullable=False)
    sender_role: Mapped[str] = mapped_column(String(32), default="Student")
    sender_initials: Mapped[str] = mapped_column(String(8), default="SN")
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    code_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_marked_as_answer: Mapped[bool] = mapped_column(Boolean, default=False)
    reactions_count: Mapped[int] = mapped_column(Integer, default=0)
    timestamp_str: Mapped[str] = mapped_column(String(32), default="10:32 AM")

class TrainerDirectThread(TenantModel):
    __tablename__ = "trainer_direct_threads"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trainer_user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"))
    contact_name: Mapped[str] = mapped_column(String(128), nullable=False) # e.g. Mr. Ramesh K
    contact_category: Mapped[str] = mapped_column(String(32), default="Parents") # Parents, College, Groups
    contact_role_chip: Mapped[str] = mapped_column(String(128), default="Parent · Priya R")
    avatar_initials: Mapped[str] = mapped_column(String(8), default="RK")
    pref_language: Mapped[str] = mapped_column(String(32), default="Prefers Tamil")
    unread_badge: Mapped[int] = mapped_column(Integer, default=0)
    last_message_preview: Mapped[str] = mapped_column(String(255), default="")
    last_message_time: Mapped[str] = mapped_column(String(32), default="10:45 AM")

class DirectMessage(TenantModel):
    __tablename__ = "direct_messages"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    thread_id: Mapped[str] = mapped_column(String(64), ForeignKey("trainer_direct_threads.id"))
    is_incoming: Mapped[bool] = mapped_column(Boolean, default=True)
    sender_name: Mapped[str] = mapped_column(String(128))
    text_en: Mapped[str] = mapped_column(Text, nullable=False)
    text_ta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp_str: Mapped[str] = mapped_column(String(32), default="10:45 AM")

# Screen 15: Parent View Monthly Cards
class ParentMonthlyRecord(TenantModel):
    __tablename__ = "parent_monthly_records"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(64), ForeignKey("students.id"))
    month_name: Mapped[str] = mapped_column(String(32), default="October")
    area: Mapped[str] = mapped_column(String(64)) # Coding, Aptitude test, Project, Communication
    prev_month_val: Mapped[str] = mapped_column(String(64))
    curr_month_val: Mapped[str] = mapped_column(String(64))
    status_text: Mapped[str] = mapped_column(String(64))
    status_color: Mapped[str] = mapped_column(String(32), default="green") # green, amber, blue

