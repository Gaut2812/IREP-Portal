import sys
import datetime
from pathlib import Path

# Add apps/api to sys.path
api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from core.database import Base, TenantModel, set_sqlite_pragma
from models.schema import (
    College, User, Student, CodingProblem,
    TestCase as TestCaseModel,
    CodingSubmission, SubmissionResult
)
from schemas.coding import (
    CodingProblemPublic, CodingProblemInternal,
    TestCaseSamplePublic as TestCaseSamplePublicDTO,
    TestCaseInternal as TestCaseInternalDTO,
    SubmissionResultPublic, SubmissionResultInternal,
    CodingSubmissionPublic, CodingSubmissionInternal
)

# In-memory SQLite engine with foreign keys enabled
@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    # Enable SQLite foreign key enforcement
    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    event.listen(Engine, "connect", set_sqlite_pragma)
    
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSessionLocal()
    
    # Seed baseline College, User, and Student in order
    col = College(id="col_demo_001", college_id="col_demo_001", name="Demo Engineering College", code="DEC")
    session.add(col)
    session.commit()

    usr = User(
        id="usr_priya_01",
        college_id="col_demo_001",
        email="priya@demo.edu",
        hashed_password="hash",
        role="student",
        name="Priya R"
    )
    session.add(usr)
    session.commit()

    std = Student(
        id="std_priya_01",
        college_id="col_demo_001",
        user_id="usr_priya_01",
        register_no="710021104042",
        branch="AI & DS"
    )
    session.add(std)
    session.commit()
    
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


# 1. Models inherit TenantModel (college_id, created_at, updated_at)
def test_models_inherit_tenant_model():
    """Verify all Screen 24 database entities inherit TenantModel audit columns."""
    for model_cls in [CodingProblem, TestCaseModel, CodingSubmission, SubmissionResult]:
        assert issubclass(model_cls, TenantModel)
        mapper = model_cls.__table__.columns
        assert "college_id" in mapper
        assert "created_at" in mapper
        assert "updated_at" in mapper
        assert mapper["college_id"].nullable is False or mapper["college_id"].default is not None


# 2. SQLite Foreign-Key Enforcement blocks orphans
def test_sqlite_foreign_key_enforcement(memory_db):
    """Verify that foreign keys are strictly enforced in SQLite."""
    # Attempt to insert a TestCase referencing a non-existent CodingProblem
    orphan_tc = TestCaseModel(
        id="tc_orphan_01",
        college_id="col_demo_001",
        problem_id="prob_non_existent",
        test_order=1,
        is_hidden=False,
        name="Orphan Case",
        input_data="[1, 2]",
        expected_output="3"
    )
    memory_db.add(orphan_tc)
    with pytest.raises(IntegrityError):
        memory_db.commit()
    memory_db.rollback()

    # Attempt to insert a CodingSubmission referencing non-existent problem
    orphan_sub = CodingSubmission(
        id="sub_orphan_01",
        college_id="col_demo_001",
        problem_id="prob_non_existent",
        student_id="std_priya_01",
        language="python",
        code="print(1)",
        status="Pending"
    )
    memory_db.add(orphan_sub)
    with pytest.raises(IntegrityError):
        memory_db.commit()
    memory_db.rollback()


# 3. Cascade Delete
def test_cascade_deletes(memory_db):
    """Verify cascade deletion from CodingProblem down to TestCase, Submission, and SubmissionResult."""
    # Create Problem
    prob = CodingProblem(
        id="prob_cascade_01",
        college_id="col_demo_001",
        slug="cascade-test",
        title="Cascade Test Problem",
        difficulty="Easy",
        topic="Testing",
        statement="Test statement",
        constraints="None"
    )
    memory_db.add(prob)
    memory_db.flush()

    # Create TestCase
    tc = TestCaseModel(
        id="tc_cascade_01",
        college_id="col_demo_001",
        problem_id=prob.id,
        test_order=1,
        is_hidden=False,
        name="Sample 1",
        input_data="1",
        expected_output="1"
    )
    memory_db.add(tc)

    # Create Submission
    sub = CodingSubmission(
        id="sub_cascade_01",
        college_id="col_demo_001",
        problem_id=prob.id,
        student_id="std_priya_01",
        language="python",
        code="return 1",
        status="Accepted"
    )
    memory_db.add(sub)
    memory_db.flush()

    # Create SubmissionResult
    res = SubmissionResult(
        id="res_cascade_01",
        college_id="col_demo_001",
        submission_id=sub.id,
        test_case_id=tc.id,
        status="Passed",
        runtime_ms=12,
        memory_mb=14.5
    )
    memory_db.add(res)
    memory_db.commit()

    # Verify rows exist
    assert memory_db.get(CodingProblem, prob.id) is not None
    assert memory_db.get(TestCaseModel, tc.id) is not None
    assert memory_db.get(CodingSubmission, sub.id) is not None
    assert memory_db.get(SubmissionResult, res.id) is not None

    # Delete CodingProblem -> TestCase, CodingSubmission, SubmissionResult must cascade delete
    memory_db.delete(prob)
    memory_db.commit()

    assert memory_db.get(CodingProblem, prob.id) is None
    assert memory_db.get(TestCaseModel, tc.id) is None
    assert memory_db.get(CodingSubmission, sub.id) is None
    assert memory_db.get(SubmissionResult, res.id) is None


# 4. Multi-Tenant Isolation
def test_tenant_isolation(memory_db):
    """Verify college-level data partitioning for coding problems and submissions."""
    # Problem in college A
    prob_a = CodingProblem(
        id="prob_col_a",
        college_id="col_demo_001",
        slug="prob-a",
        title="College A Problem",
        difficulty="Easy",
        topic="Math",
        statement="A stmt",
        constraints="none"
    )
    # Problem in college B
    prob_b = CodingProblem(
        id="prob_col_b",
        college_id="col_other_999",
        slug="prob-b",
        title="College B Problem",
        difficulty="Hard",
        topic="Math",
        statement="B stmt",
        constraints="none"
    )
    memory_db.add_all([prob_a, prob_b])
    memory_db.commit()

    # Query scoped to col_demo_001
    results = memory_db.execute(
        select(CodingProblem).filter(CodingProblem.college_id == "col_demo_001")
    ).scalars().all()

    assert len(results) == 1
    assert results[0].id == "prob_col_a"
    assert "col_other_999" not in [r.college_id for r in results]


# 5. Hidden vs Sample TestCase Separation
def test_hidden_and_sample_test_case_partitioning(memory_db):
    """Verify clear partition between sample (is_hidden=False) and hidden (is_hidden=True) test cases."""
    prob = CodingProblem(
        id="prob_tc_partition",
        college_id="col_demo_001",
        slug="partition-test",
        title="Partition Test",
        difficulty="Medium",
        topic="Graphs",
        statement="Graph components",
        constraints="N <= 1000"
    )
    memory_db.add(prob)
    memory_db.flush()

    tc1 = TestCaseModel(
        id="tc_sample_01",
        college_id="col_demo_001",
        problem_id=prob.id,
        test_order=1,
        is_hidden=False,
        name="Public Sample 1",
        input_data="5\n[[0,1]]",
        expected_output="4"
    )
    tc2 = TestCaseModel(
        id="tc_hidden_01",
        college_id="col_demo_001",
        problem_id=prob.id,
        test_order=2,
        is_hidden=True,
        name="Secret Corner Case",
        input_data="1000\n[]",
        expected_output="1000"
    )
    memory_db.add_all([tc1, tc2])
    memory_db.commit()

    sample_tests = memory_db.execute(
        select(TestCaseModel).filter(TestCaseModel.problem_id == prob.id, TestCaseModel.is_hidden == False)
    ).scalars().all()
    hidden_tests = memory_db.execute(
        select(TestCaseModel).filter(TestCaseModel.problem_id == prob.id, TestCaseModel.is_hidden == True)
    ).scalars().all()

    assert len(sample_tests) == 1
    assert sample_tests[0].id == "tc_sample_01"
    assert sample_tests[0].is_hidden is False

    assert len(hidden_tests) == 1
    assert hidden_tests[0].id == "tc_hidden_01"
    assert hidden_tests[0].is_hidden is True


# 6. Student-facing vs Internal Pydantic Schema Security (Zero Leakage)
def test_pydantic_schema_zero_leakage():
    """Verify student-facing response schemas NEVER leak hidden inputs, expected outputs, or hidden actual output."""
    tc_hidden = TestCaseModel(
        id="tc_secret_99",
        college_id="col_demo_001",
        problem_id="prob_01",
        test_order=99,
        is_hidden=True,
        name="Secret Stress Test",
        input_data="CRITICAL_SECRET_INPUT",
        expected_output="CRITICAL_SECRET_OUTPUT",
        explanation="Secret explanation"
    )
    tc_sample = TestCaseModel(
        id="tc_public_01",
        college_id="col_demo_001",
        problem_id="prob_01",
        test_order=1,
        is_hidden=False,
        name="Public Sample",
        input_data="1 2",
        expected_output="3",
        explanation="Public explanation"
    )

    # 6a. TestCaseSamplePublicDTO does not even have fields for internal flags or hidden secrets
    sample_dto = TestCaseSamplePublicDTO.model_validate(tc_sample)
    assert sample_dto.input_data == "1 2"
    assert sample_dto.expected_output == "3"

    # 6b. Problem with mixed tests -> CodingProblemPublic automatically filters out hidden tests
    prob = CodingProblem(
        id="prob_01",
        college_id="col_demo_001",
        slug="leak-test",
        title="Zero Leak Problem",
        difficulty="Hard",
        topic="Security",
        statement="Statement text",
        constraints="None",
        time_limit_ms=1000,
        memory_limit_mb=256,
        test_cases=[tc_sample, tc_hidden]
    )

    public_prob_dto = CodingProblemPublic.model_validate(prob)
    assert len(public_prob_dto.sample_test_cases) == 1
    assert public_prob_dto.sample_test_cases[0].id == "tc_public_01"
    # Ensure hidden case is not present in public schema anywhere
    public_dict = public_prob_dto.model_dump()
    assert "CRITICAL_SECRET_INPUT" not in str(public_dict)
    assert "CRITICAL_SECRET_OUTPUT" not in str(public_dict)

    # 6c. SubmissionResult for hidden test case must sanitize actual_output and error_output
    sub_res_hidden = SubmissionResult(
        id="res_hidden_01",
        college_id="col_demo_001",
        submission_id="sub_01",
        test_case_id=tc_hidden.id,
        test_case=tc_hidden,
        status="Wrong Answer",
        runtime_ms=15,
        memory_mb=12.2,
        actual_output="LEAKED_STUDENT_OUTPUT_DATA",
        error_output="Internal execution trace at line 42"
    )

    public_res_dto = SubmissionResultPublic.model_validate(sub_res_hidden)
    # actual_output must be masked / None for hidden tests
    assert public_res_dto.actual_output is None
    # error_output must be sanitized for hidden tests
    assert "line 42" not in (public_res_dto.error_output or "")
    assert public_res_dto.status == "Wrong Answer"

    # Internal schema retains full diagnostic details for grading engine / trainer
    internal_res_dto = SubmissionResultInternal.model_validate(sub_res_hidden)
    assert internal_res_dto.actual_output == "LEAKED_STUDENT_OUTPUT_DATA"
    assert "line 42" in internal_res_dto.error_output


# 7. PostgreSQL Dialect DDL Compilation & Compatibility
def test_postgresql_ddl_compilation():
    """Verify that all Screen 24 models generate valid PostgreSQL DDL with proper constraints."""
    for model_cls in [CodingProblem, TestCaseModel, CodingSubmission, SubmissionResult]:
        ddl = str(CreateTable(model_cls.__table__).compile(dialect=postgresql.dialect()))
        assert "CREATE TABLE" in ddl
        assert model_cls.__tablename__ in ddl
        # Check foreign keys and constraints compile cleanly
        if model_cls in [TestCaseModel, CodingSubmission, SubmissionResult]:
            assert "FOREIGN KEY" in ddl or "REFERENCES" in ddl


# 8. Alembic Migration Structure and Revisions
def test_alembic_migration_integrity():
    """Verify Alembic migration revision script exists, defines upgrade/downgrade, and has valid tables."""
    migration_file = Path(api_dir) / "alembic" / "versions" / "0001_screen24_coding_foundation.py"
    assert migration_file.exists(), "Alembic migration file not found"
    
    content = migration_file.read_text(encoding="utf-8")
    assert "def upgrade()" in content
    assert "def downgrade()" in content
    assert "coding_problems" in content
    assert "test_cases" in content
    assert "coding_submissions" in content
    assert "submission_results" in content
    assert "college_id" in content
    assert "is_hidden" in content
