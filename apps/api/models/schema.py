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
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)

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
    # S0 cohort structure
    branch_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("branches.id"), nullable=True, index=True)
    batch_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("batches.id"), nullable=True, index=True)
    track: Mapped[str] = mapped_column(String(64), default="AI & Data Science")
    academic_year: Mapped[str] = mapped_column(String(16), default="2026-27")

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
    batch_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("batches.id"), nullable=True, index=True)
    week_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

class SessionAttendance(TenantModel):
    __tablename__ = "session_attendance"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("sessions.id"))
    student_id: Mapped[str] = mapped_column(String(64), ForeignKey("students.id"))
    minutes_present: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="Present") # Present, Absent, Partial
    marked_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    source: Mapped[str] = mapped_column(String(16), default="auto")   # auto (75% rule), qr, manual
    overridden_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

# Screen 24: Coding Lab
class CodingProblem(TenantModel):
    __tablename__ = "coding_problems"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    slug: Mapped[Optional[str]] = mapped_column(String(128), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(32), default="Medium", index=True)
    topic: Mapped[str] = mapped_column(String(64), default="Union-Find", index=True)
    company_tags: Mapped[str] = mapped_column(String(255), default="Product cos.")
    week_info: Mapped[str] = mapped_column(String(128), default="Week 8 · Pattern drill · 3 of 6 solved")
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    example_input: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    example_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    constraints: Mapped[str] = mapped_column(Text, nullable=False)
    time_limit_ms: Mapped[int] = mapped_column(Integer, default=2000)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, default=256)
    starter_codes: Mapped[dict] = mapped_column(JSON, default=dict)
    starter_code: Mapped[str] = mapped_column(Text, default="")
    trainer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trainer_author: Mapped[str] = mapped_column(String(128), default="Arun K.")

    # Relationships
    test_cases: Mapped[List["TestCase"]] = relationship(
        "TestCase", back_populates="problem", cascade="all, delete-orphan", order_by="TestCase.test_order"
    )
    submissions: Mapped[List["CodingSubmission"]] = relationship(
        "CodingSubmission", back_populates="problem", cascade="all, delete-orphan"
    )

class TestCase(TenantModel):
    __tablename__ = "test_cases"
    __test__ = False
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    problem_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("coding_problems.id", ondelete="CASCADE"), index=True, nullable=False
    )
    test_order: Mapped[int] = mapped_column(Integer, default=1)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    input_data: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    problem: Mapped["CodingProblem"] = relationship("CodingProblem", back_populates="test_cases")
    submission_results: Mapped[List["SubmissionResult"]] = relationship(
        "SubmissionResult", back_populates="test_case", cascade="all, delete-orphan"
    )

class CodingSubmission(TenantModel):
    __tablename__ = "coding_submissions"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    problem_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("coding_problems.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    language: Mapped[str] = mapped_column(String(32), default="python")
    code: Mapped[str] = mapped_column(Text, nullable=False)
    runtime_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=42)
    memory_mb: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=16.1)
    status: Mapped[str] = mapped_column(String(32), default="Pending", index=True)
    tests_passed: Mapped[int] = mapped_column(Integer, default=0)
    tests_total: Mapped[int] = mapped_column(Integer, default=0)
    hints_used: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    problem: Mapped["CodingProblem"] = relationship("CodingProblem", back_populates="submissions")
    student: Mapped["Student"] = relationship("Student")
    results: Mapped[List["SubmissionResult"]] = relationship(
        "SubmissionResult", back_populates="submission", cascade="all, delete-orphan"
    )

class SubmissionResult(TenantModel):
    __tablename__ = "submission_results"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    submission_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("coding_submissions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    test_case_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("test_cases.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    runtime_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    memory_mb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    submission: Mapped["CodingSubmission"] = relationship("CodingSubmission", back_populates="results")
    test_case: Mapped["TestCase"] = relationship("TestCase", back_populates="submission_results")

class CodingHintUsage(TenantModel):
    __tablename__ = "coding_hint_usages"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    problem_id: Mapped[str] = mapped_column(String(64), ForeignKey("coding_problems.id", ondelete="CASCADE"))
    student_id: Mapped[str] = mapped_column(String(64), ForeignKey("students.id", ondelete="CASCADE"))
    hint_number: Mapped[int] = mapped_column(Integer, default=1)
    hint_text: Mapped[str] = mapped_column(Text)

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

# Screen 32: Student Portfolio Projects
class StudentProject(TenantModel):
    __tablename__ = "student_projects"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(64), ForeignKey("students.id"))
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    tagline: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    category: Mapped[str] = mapped_column(String(64), default="machine_learning") # machine_learning, fullstack, iot, cloud
    description: Mapped[str] = mapped_column(Text, nullable=False)
    parent_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    role_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    team_size: Mapped[int] = mapped_column(Integer, default=1)
    team_name: Mapped[str] = mapped_column(String(64), default="Team Phoenix")
    tech_stack: Mapped[str] = mapped_column(Text, default="[]") # JSON list of strings
    github_url: Mapped[str] = mapped_column(String(255), nullable=False)
    live_demo_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="deployed") # deployed, completed, in_progress, review
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    trainer_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    trainer_name: Mapped[str] = mapped_column(String(128), default="Arun Kumar")
    trainer_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    score_percent: Mapped[int] = mapped_column(Integer, default=92)

# Screen 32: Verified Skills & Badges
class StudentSkill(TenantModel):
    __tablename__ = "student_skills"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(64), ForeignKey("students.id"))
    skill_name: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(32), default="Core CS")
    level: Mapped[str] = mapped_column(String(32), default="Gold") # Gold, Silver, Advanced, Proficient
    problems_solved: Mapped[int] = mapped_column(Integer, default=0)
    verified_by: Mapped[str] = mapped_column(String(128), default="Arun Kumar")

# Screen 33: Parent Project Demo Day Event
class ProjectDemoEvent(TenantModel):
    __tablename__ = "project_demo_events"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    event_date: Mapped[str] = mapped_column(String(64), nullable=False)
    venue: Mapped[str] = mapped_column(String(128), default="Auditorium A & Live Stream")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    rsvp_status: Mapped[str] = mapped_column(String(32), default="none") # none, attending, declined
    guest_count: Mapped[int] = mapped_column(Integer, default=1)

# Screen 31: Trainer Code Reviews (Pull Requests)
class PullRequest(TenantModel):
    __tablename__ = "pull_requests"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    pr_number: Mapped[str] = mapped_column(String(32), nullable=False) # e.g. "#39", "#41"
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), default="proj_clinic_02")
    project_name: Mapped[str] = mapped_column(String(128), default="Clinic Appointment System")
    team_name: Mapped[str] = mapped_column(String(64), default="Team Phoenix")
    task_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("sprint_tasks.id"), nullable=True)
    author_id: Mapped[str] = mapped_column(String(64), ForeignKey("students.id"))
    author_name: Mapped[str] = mapped_column(String(128), default="Priya R")
    author_initials: Mapped[str] = mapped_column(String(8), default="PR")
    source_branch: Mapped[str] = mapped_column(String(64), default="feat/booking-tests")
    target_branch: Mapped[str] = mapped_column(String(64), default="main")
    status: Mapped[str] = mapped_column(String(32), default="pending") # pending, approved, changes_requested
    story_points: Mapped[int] = mapped_column(Integer, default=3)
    automated_checks_passed: Mapped[bool] = mapped_column(Boolean, default=True)
    automated_checks_summary: Mapped[str] = mapped_column(String(255), default="14/14 tests passing · Lint clean")
    diff_summary: Mapped[str] = mapped_column(String(128), default="+142 -28 across 2 files")
    review_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    code_quality_score: Mapped[Optional[int]] = mapped_column(Integer, default=5)
    test_coverage_score: Mapped[Optional[int]] = mapped_column(Integer, default=5)
    modularity_score: Mapped[Optional[int]] = mapped_column(Integer, default=4)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

class PullRequestFile(TenantModel):
    __tablename__ = "pull_request_files"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    pr_id: Mapped[str] = mapped_column(String(64), ForeignKey("pull_requests.id"))
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    change_type: Mapped[str] = mapped_column(String(32), default="modified") # modified, added, deleted
    additions: Mapped[int] = mapped_column(Integer, default=0)
    deletions: Mapped[int] = mapped_column(Integer, default=0)
    diff_content: Mapped[str] = mapped_column(Text, nullable=False)

class PullRequestComment(TenantModel):
    __tablename__ = "pull_request_comments"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    pr_id: Mapped[str] = mapped_column(String(64), ForeignKey("pull_requests.id"))
    file_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    line_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    author_name: Mapped[str] = mapped_column(String(128), default="Arun Kumar")
    author_role: Mapped[str] = mapped_column(String(32), default="Trainer")
    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)




# ---------------------------------------------------------------------------
# S0 Foundation: college structure, cohort, governance
# ---------------------------------------------------------------------------
from sqlalchemy import UniqueConstraint, Date


class Branch(TenantModel):
    __tablename__ = "branches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)      # CSE, IT, AI & DS, Cybersecurity
    code: Mapped[str] = mapped_column(String(32), nullable=False)       # CSE, IT, AIDS, CYB
    track: Mapped[str] = mapped_column(String(64), default="Software Engineering")
    hod_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


class Batch(TenantModel):
    __tablename__ = "batches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    branch_id: Mapped[str] = mapped_column(String(64), ForeignKey("branches.id"), index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)      # CSE-A · Sem 5
    short_name: Mapped[str] = mapped_column(String(32), nullable=False) # CSE-A
    semester: Mapped[int] = mapped_column(Integer, default=5, index=True)
    academic_year: Mapped[str] = mapped_column(String(16), default="2026-27")
    track: Mapped[str] = mapped_column(String(64), default="Software Engineering")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BatchTrainer(TenantModel):
    __tablename__ = "batch_trainers"
    __table_args__ = (UniqueConstraint("batch_id", "trainer_id", name="uq_batch_trainer"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), ForeignKey("batches.id"), index=True)
    trainer_id: Mapped[str] = mapped_column(String(64), ForeignKey("trainers.id"), index=True)
    role: Mapped[str] = mapped_column(String(32), default="primary")   # primary, substitute


class Certificate(TenantModel):
    __tablename__ = "certificates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(64), ForeignKey("students.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    issuer: Mapped[str] = mapped_column(String(128), default="IREP")
    cert_type: Mapped[str] = mapped_column(String(32), default="course")   # course, external, exam
    status: Mapped[str] = mapped_column(String(32), default="earned", index=True)  # earned, scheduled, pending_proof, revoked
    issued_on: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True, index=True)
    exam_date: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    verify_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    proof_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)


class Internship(TenantModel):
    __tablename__ = "internships"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(64), ForeignKey("students.id"), index=True)
    company: Mapped[str] = mapped_column(String(128), nullable=False)
    role_title: Mapped[str] = mapped_column(String(128), default="Software Intern")
    status: Mapped[str] = mapped_column(String(32), default="secured")  # secured, offered, completed
    semester: Mapped[int] = mapped_column(Integer, default=6)
    secured_on: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)


class AuditLog(TenantModel):
    """Append-only audit trail for sensitive actions (P04)."""
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)   # login.success, rsvp.save, ...
    entity_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    detail: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class OtpAttempt(TenantModel):
    __tablename__ = "otp_attempts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    phone_hash: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    otp_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    verify_attempts: Mapped[int] = mapped_column(Integer, default=0)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)


class Notification(TenantModel):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(64), default="info")  # info, approval, message, event, report, reminder
    title_en: Mapped[str] = mapped_column(String(255), nullable=False)
    title_ta: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    body_en: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body_ta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    link: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), default="in_app")  # in_app, sms, email
    delivery_status: Mapped[str] = mapped_column(String(32), default="delivered")
    read_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# Screen 12: readiness snapshots, skill scores, badges, events
# ---------------------------------------------------------------------------

class ReadinessConfig(TenantModel):
    """Per-college weights (sum to 1.0) and band thresholds (P09)."""
    __tablename__ = "readiness_config"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    weights: Mapped[dict] = mapped_column(JSON, default=dict)        # {"dsa": 0.25, ...}
    band_ready_min: Mapped[int] = mapped_column(Integer, default=75)
    band_nearly_min: Mapped[int] = mapped_column(Integer, default=60)
    version: Mapped[int] = mapped_column(Integer, default=1)


class SkillScore(TenantModel):
    __tablename__ = "skill_scores"
    __table_args__ = (UniqueConstraint("student_id", "skill_key", name="uq_skill_score_student_skill"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(64), ForeignKey("students.id"), index=True)
    skill_key: Mapped[str] = mapped_column(String(32), nullable=False)   # dsa, aptitude, cloud, track, future_skills, communication
    label_en: Mapped[str] = mapped_column(String(128), nullable=False)
    label_ta: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    percentage: Mapped[int] = mapped_column(Integer, default=0)
    color: Mapped[str] = mapped_column(String(16), default="teal")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class ReadinessSnapshot(TenantModel):
    __tablename__ = "readiness_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(64), ForeignKey("students.id"), index=True)
    snapshot_date: Mapped[datetime.date] = mapped_column(Date, index=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    band: Mapped[str] = mapped_column(String(32), default="Needs Support")
    delta: Mapped[int] = mapped_column(Integer, default=0)
    breakdown: Mapped[dict] = mapped_column(JSON, default=dict)      # [{"key","label","value","weight","contribution"}]
    config_version: Mapped[int] = mapped_column(Integer, default=1)


class Badge(TenantModel):
    __tablename__ = "badges"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name_en: Mapped[str] = mapped_column(String(128), nullable=False)
    name_ta: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    description_en: Mapped[str] = mapped_column(String(255), nullable=False)
    description_ta: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    icon: Mapped[str] = mapped_column(String(16), default="star")   # emoji or icon key
    rule: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class StudentBadge(TenantModel):
    __tablename__ = "student_badges"
    __table_args__ = (UniqueConstraint("student_id", "badge_id", name="uq_student_badge"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(64), ForeignKey("students.id"), index=True)
    badge_id: Mapped[str] = mapped_column(String(64), ForeignKey("badges.id"), index=True)
    earned_on: Mapped[datetime.date] = mapped_column(Date)


class Event(TenantModel):
    """Calendar events shared by screens 12, 15, 17, 19, 42."""
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title_en: Mapped[str] = mapped_column(String(255), nullable=False)
    title_ta: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    kind: Mapped[str] = mapped_column(String(32), default="event", index=True)  # test, interview, exam, drive, demo_day, meeting, guest
    starts_at: Mapped[datetime.datetime] = mapped_column(DateTime, index=True)
    ends_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    audience: Mapped[str] = mapped_column(String(32), default="students")  # students, parents, all, college
    batch_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    student_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)  # personal items (own exam/interview)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description_en: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description_ta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rsvp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


# ---------------------------------------------------------------------------
# Screen 13/14: at-risk flags and rule configuration
# ---------------------------------------------------------------------------

class RulesConfig(TenantModel):
    __tablename__ = "rules_config"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    score_below: Mapped[int] = mapped_column(Integer, default=60)
    attendance_below: Mapped[int] = mapped_column(Integer, default=75)
    missed_sessions: Mapped[int] = mapped_column(Integer, default=3)
    project_delay_days: Mapped[int] = mapped_column(Integer, default=7)
    quiet_hours_start: Mapped[int] = mapped_column(Integer, default=21)   # parent alerts are held between 21:00 and 08:00
    quiet_hours_end: Mapped[int] = mapped_column(Integer, default=8)


class AtRiskFlag(TenantModel):
    __tablename__ = "at_risk_flags"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(64), ForeignKey("students.id"), index=True)
    batch_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    reason_key: Mapped[str] = mapped_column(String(32), nullable=False, index=True)   # low_score, low_attendance, missed_sessions, project_delay
    reason_text: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="medium")                # low, medium, high
    suggested_action: Mapped[str] = mapped_column(String(32), default="mentor")        # parent_call, extra_saturday, mentor
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)        # open, in_progress, resolved
    parent_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_notified_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resolved_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    flagged_on: Mapped[datetime.date] = mapped_column(Date, default=datetime.date.today)


class FlagAction(TenantModel):
    __tablename__ = "flag_actions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    flag_id: Mapped[str] = mapped_column(String(64), ForeignKey("at_risk_flags.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)   # parent_call, extra_saturday, mentor, note, resolve
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    actor_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


# ---------------------------------------------------------------------------
# Screen 19/20: MoU report runs
# ---------------------------------------------------------------------------

class ReportRun(TenantModel):
    __tablename__ = "report_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title_en: Mapped[str] = mapped_column(String(255), nullable=False)
    title_ta: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    report_type: Mapped[str] = mapped_column(String(32), default="progress")   # progress, performance, readiness
    period_label: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    generated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    data_as_of: Mapped[datetime.date] = mapped_column(Date, default=datetime.date.today)
    file_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)   # relative to the API static dir
    file_size_kb: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="ready")   # queued, running, ready, failed
    generated_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


# ---------------------------------------------------------------------------
# Screen 15/16/17: parent monthly cards and RSVPs
# ---------------------------------------------------------------------------

class MonthlyCard(TenantModel):
    """One parent progress card per student per month. Released to parents only
    when status is approved or sent (trainer approval, Screen 21)."""
    __tablename__ = "monthly_cards"
    __table_args__ = (UniqueConstraint("student_id", "year", "month", name="uq_monthly_card_student_month"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(64), ForeignKey("students.id"), index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    rows: Mapped[list] = mapped_column(JSON, default=list)   # [{area_en, area_ta, prev, curr, status_en, status_ta, color}]
    how_to_help_en: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    how_to_help_ta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trainer_remark_en: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trainer_remark_ta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trainer_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)   # draft, approved, sent
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)


class Rsvp(TenantModel):
    __tablename__ = "rsvps"
    __table_args__ = (UniqueConstraint("event_id", "parent_user_id", name="uq_rsvp_event_parent"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), ForeignKey("events.id"), index=True)
    parent_user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), index=True)
    student_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="yes")   # yes, no, maybe
    guests: Mapped[int] = mapped_column(Integer, default=1)


# ---------------------------------------------------------------------------
# Screen 08: recordings, reminders, recording views
# ---------------------------------------------------------------------------

class Recording(TenantModel):
    __tablename__ = "recordings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("sessions.id"), nullable=True, index=True)
    batch_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)       # object-storage key; served via signed URL
    duration_min: Mapped[int] = mapped_column(Integer, default=60)
    chapters: Mapped[list] = mapped_column(JSON, default=list)                  # [{"at_sec": 0, "title": "..."}]
    has_transcript: Mapped[bool] = mapped_column(Boolean, default=False)
    has_summary: Mapped[bool] = mapped_column(Boolean, default=False)
    recorded_on: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="ready")           # processing, ready


class SessionReminder(TenantModel):
    __tablename__ = "reminders"
    __table_args__ = (UniqueConstraint("user_id", "session_id", name="uq_reminder_user_session"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), index=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("sessions.id"), index=True)
    channel: Mapped[str] = mapped_column(String(16), default="in_app")
    remind_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)


class RecordingView(TenantModel):
    __tablename__ = "recording_views"
    __table_args__ = (UniqueConstraint("student_id", "recording_id", name="uq_recording_view"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(64), ForeignKey("students.id"), index=True)
    recording_id: Mapped[str] = mapped_column(String(64), ForeignKey("recordings.id"), index=True)
    watched_seconds: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------------------------------------------------------------------
# Screen 07: live classroom (meetings, join events, polls, Q&A)
# ---------------------------------------------------------------------------

class LiveMeeting(TenantModel):
    __tablename__ = "live_meetings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("sessions.id"), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(16), default="fake")            # fake, bbb
    external_meeting_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    started_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    is_recording: Mapped[bool] = mapped_column(Boolean, default=True)
    sharing_user_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    shared_file: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    shared_source: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    shared_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    flow_title: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    flow_steps: Mapped[list] = mapped_column(JSON, default=list)
    finalized: Mapped[bool] = mapped_column(Boolean, default=False)


class JoinEvent(TenantModel):
    __tablename__ = "join_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("sessions.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), index=True)
    event: Mapped[str] = mapped_column(String(16), nullable=False)               # joined, left
    at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(16), default="portal")            # portal, webhook


class LivePoll(TenantModel):
    __tablename__ = "live_polls"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("sessions.id"), index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list] = mapped_column(JSON, default=list)                    # [{"key":"a","text":"...","color":"red"}]
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class LivePollVote(TenantModel):
    __tablename__ = "live_poll_votes"
    __table_args__ = (UniqueConstraint("poll_id", "user_id", name="uq_poll_vote_user"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    poll_id: Mapped[str] = mapped_column(String(64), ForeignKey("live_polls.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    option_key: Mapped[str] = mapped_column(String(8), nullable=False)


class QaQuestion(TenantModel):
    __tablename__ = "qa_questions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("sessions.id"), index=True)
    author_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    author_name: Mapped[str] = mapped_column(String(128), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    answered_at_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)


class QaUpvote(TenantModel):
    __tablename__ = "qa_upvotes"
    __table_args__ = (UniqueConstraint("question_id", "user_id", name="uq_qa_upvote_user"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    question_id: Mapped[str] = mapped_column(String(64), ForeignKey("qa_questions.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
