import datetime
from sqlalchemy import select
from core.database import SessionLocal, engine, Base
from core.security import get_password_hash
from models.schema import (
    College, User, Student, Trainer, ParentStudent,
    SessionItem, SessionAttendance, CodingProblem, TestCase, CodingSubmission, SubmissionResult,
    PracticeTest, PracticeQuestion, VirtualLabItem, SprintTask,
    MockInterview, DiscussionGroup, GroupMessage, TrainerDirectThread,
    DirectMessage, ParentMonthlyRecord, TestAttempt, AttemptAnswer,
    ProctorEvent, TopicScore
)

def get_screen24_test_cases():
    cases = [
        TestCase(
            id="tc_demo_01",
            college_id="col_demo_001",
            problem_id="prob_connected_components",
            test_order=1,
            is_hidden=False,
            name="Sample Case 1",
            input_data="5\n[[0,1],[1,2],[3,4]]",
            expected_output="2",
            explanation="Nodes 0, 1, 2 form one component and nodes 3, 4 form another component."
        ),
        TestCase(
            id="tc_demo_02",
            college_id="col_demo_001",
            problem_id="prob_connected_components",
            test_order=2,
            is_hidden=False,
            name="Sample Case 2",
            input_data="5\n[[0,1],[1,2],[2,3],[3,4]]",
            expected_output="1",
            explanation="All nodes are connected in a single component."
        ),
    ]
    hidden_specs = [
        (3, "Hidden Boundary: Disconnected Singletons", "5\n[]", "5", "No edges."),
        (4, "Hidden Edge: Large Component Cycle", "4\n[[2,3],[1,2],[1,3]]", "2", "1 isolated, 3 cyclic."),
        (5, "Hidden Stress: Single Node", "1\n[]", "1", "Trivial 1-node graph."),
        (6, "Hidden Pair: 2 Nodes Connected", "2\n[[0,1]]", "1", "Simple pair connected."),
        (7, "Hidden Pair: 2 Nodes Disconnected", "2\n[]", "2", "Simple pair disconnected."),
        (8, "Hidden Star: Hub and Spokes", "6\n[[0,1],[0,2],[0,3],[0,4],[0,5]]", "1", "Star graph."),
        (9, "Hidden Multi-cycle: Two Separate Triangles", "6\n[[0,1],[1,2],[2,0],[3,4],[4,5],[5,3]]", "2", "Two triangles."),
        (10, "Hidden Chain: Linear Line", "7\n[[0,1],[1,2],[2,3],[3,4],[4,5],[5,6]]", "1", "Linear line."),
        (11, "Hidden Forest: 3 Trees", "9\n[[0,1],[2,3],[4,5],[6,7]]", "5", "4 pairs + 1 isolated."),
        (12, "Hidden Complete: K4", "4\n[[0,1],[0,2],[0,3],[1,2],[1,3],[2,3]]", "1", "Fully connected."),
        (13, "Hidden Bipartite", "6\n[[0,3],[0,4],[1,3],[1,5],[2,4],[2,5]]", "1", "Bipartite graph."),
        (14, "Hidden Dense with Redundant Edges", "5\n[[0,1],[1,0],[0,2],[2,0],[1,2]]", "3", "Redundant edges."),
        (15, "Hidden Permutation Sequence", "8\n[[7,6],[6,5],[5,4],[3,2],[2,1]]", "3", "2 chains + 1 isolated."),
        (16, "Hidden Large Sparse", "10\n[[0,9],[1,8],[2,7]]", "7", "3 pairs + 4 isolated."),
        (17, "Hidden Wheel Graph", "5\n[[0,1],[1,2],[2,3],[3,0],[4,0],[4,1],[4,2],[4,3]]", "1", "Wheel."),
        (18, "Hidden Scale Test (n=2000)", "2000\n[[0,1],[1,2]]", "1998", "Max constraints boundary.")
    ]
    for order, name, inp, exp, expl in hidden_specs:
        cases.append(
            TestCase(
                id=f"tc_demo_{order:02d}",
                college_id="col_demo_001",
                problem_id="prob_connected_components",
                test_order=order,
                is_hidden=True,
                name=name,
                input_data=inp,
                expected_output=exp,
                explanation=expl
            )
        )
    return cases

def init_db_and_seed():
    print("Creating tables...", flush=True)
    Base.metadata.create_all(engine)
        
    db = SessionLocal()
    try:
        # Check if already seeded
        result = db.execute(select(College).filter_by(id="col_demo_001")).scalar_one_or_none()
        if result:
            # Check if all 18 TestCases are present for the problem
            tc_existing = db.execute(select(TestCase).filter_by(problem_id="prob_connected_components")).scalars().all()
            if len(tc_existing) < 18:
                print("Seeding full suite of 18 TestCases for Screen 24 Coding Lab...", flush=True)
                existing_ids = {tc.id for tc in tc_existing}
                for tc in get_screen24_test_cases():
                    if tc.id not in existing_ids:
                        db.add(tc)
                db.commit()
                print("18 TestCases verified and committed.", flush=True)
            print("Database already seeded.", flush=True)
            return

        print("Seeding database with demo data matching PDF mockups...", flush=True)
        
        # 1. College
        college = College(
            id="col_demo_001",
            college_id="col_demo_001",
            name="Demo Engineering College",
            code="DEC",
            logo_url="/logo.png"
        )
        db.add(college)
        
        # 2. Users
        student_user = User(
            id="usr_priya_01",
            college_id="col_demo_001",
            email="priya.r@demo.edu",
            hashed_password=get_password_hash("password123"),
            role="student",
            name="Priya R",
            phone="9876543211",
            avatar_initials="PR",
            language_pref="en"
        )
        trainer_user = User(
            id="usr_arun_01",
            college_id="col_demo_001",
            email="arun.k@demo.edu",
            hashed_password=get_password_hash("password123"),
            role="trainer",
            name="Arun Kumar",
            phone="9876543212",
            avatar_initials="AK",
            language_pref="en"
        )
        college_user = User(
            id="usr_kavitha_01",
            college_id="col_demo_001",
            email="admin@demo.edu",
            hashed_password=get_password_hash("password123"),
            role="college_admin",
            name="Dr. Kavitha",
            phone="9876543213",
            avatar_initials="DC",
            language_pref="en"
        )
        parent_user = User(
            id="usr_ramesh_01",
            college_id="col_demo_001",
            email="ramesh.k@example.com",
            hashed_password=get_password_hash("password123"),
            role="parent",
            name="Mr. Ramesh K",
            phone="9876543210",
            avatar_initials="RK",
            language_pref="ta"
        )
        db.add_all([student_user, trainer_user, college_user, parent_user])
        db.flush()
        
        # 3. Student & Trainer Profiles
        student_profile = Student(
            id="std_priya_01",
            college_id="col_demo_001",
            user_id="usr_priya_01",
            register_no="910022104042",
            branch="AI & DS",
            semester=5,
            batch_name="AI & DS · Sem 5 Batch",
            readiness_score=74,
            readiness_band="Nearly Ready",
            readiness_delta=6,
            problems_solved=286,
            attendance_pct=92,
            streak_days=19
        )
        trainer_profile = Trainer(
            id="trn_arun_01",
            college_id="col_demo_001",
            user_id="usr_arun_01",
            designation="Senior Technical Trainer",
            specialization="AI & Cloud Systems"
        )
        parent_student = ParentStudent(
            id="ps_ramesh_priya",
            college_id="col_demo_001",
            parent_user_id="usr_ramesh_01",
            student_id="std_priya_01",
            relationship="Father"
        )
        db.add_all([student_profile, trainer_profile, parent_student])
        
        # 4. Coding Problem (Screen 24 - PDF 3)
        problem = CodingProblem(
            id="prob_connected_components",
            college_id="col_demo_001",
            slug="connected-components",
            title="Number of Connected Components in an Undirected Graph",
            difficulty="Medium",
            topic="Union-Find",
            company_tags="Product cos.",
            week_info="Week 8 · Pattern drill · 3 of 6 solved",
            statement="You have a graph of n nodes. You are given an integer n and an array edges where edges[i] = [ai, bi] indicates that there is an edge between ai and bi in the graph.\n\nReturn the number of connected components in the graph.",
            constraints="1 <= n <= 2000\n0 <= edges.length <= 5000\nedges[i].length == 2\n0 <= ai <= bi < n\nai != bi\nThere are no repeated edges.",
            time_limit_ms=2000,
            memory_limit_mb=256,
            starter_code="class Solution:\n    def countComponents(self, n: int, edges: list[list[int]]) -> int:\n        parent = list(range(n))\n        \n        def find(x):\n            if parent[x] != x:\n                parent[x] = find(parent[x])\n            return parent[x]\n            \n        def union(x, y):\n            rx, ry = find(x), find(y)\n            if rx != ry:\n                parent[rx] = ry\n                return 1\n            return 0\n            \n        return n - sum(union(u, v) for u, v in edges)",
            trainer_notes="Notice how path compression in find() flattens the tree. For best worst-case complexity, add union-by-rank.",
            trainer_author="Arun K."
        )
        db.add(problem)
        db.flush()
        
        # 4b. Test Cases (Sample + Hidden)
        test_cases = [
            TestCase(
                id="tc_demo_01",
                college_id="col_demo_001",
                problem_id="prob_connected_components",
                test_order=1,
                is_hidden=False,
                name="Sample Case 1",
                input_data="5\n[[0,1],[1,2],[3,4]]",
                expected_output="2",
                explanation="Nodes 0, 1, 2 form one component and nodes 3, 4 form another component."
            ),
            TestCase(
                id="tc_demo_02",
                college_id="col_demo_001",
                problem_id="prob_connected_components",
                test_order=2,
                is_hidden=False,
                name="Sample Case 2",
                input_data="5\n[[0,1],[1,2],[2,3],[3,4]]",
                expected_output="1",
                explanation="All nodes are connected in a single component."
            ),
            TestCase(
                id="tc_demo_03",
                college_id="col_demo_001",
                problem_id="prob_connected_components",
                test_order=3,
                is_hidden=True,
                name="Hidden Boundary: Disconnected Singletons",
                input_data="5\n[]",
                expected_output="5",
                explanation="Graph has no edges; all nodes are separate components."
            ),
            TestCase(
                id="tc_demo_04",
                college_id="col_demo_001",
                problem_id="prob_connected_components",
                test_order=4,
                is_hidden=True,
                name="Hidden Edge: Large Component Cycle",
                input_data="4\n[[2,3],[1,2],[1,3]]",
                expected_output="2",
                explanation="Node 0 is isolated, nodes 1, 2, 3 form a cyclic component."
            )
        ]
        db.add_all(test_cases)
        
        # 5. Practice Test (Screen 23 - PDF 4)
        test = PracticeTest(
            id="test_service_aptitude",
            college_id="col_demo_001",
            title="Practice Test: Service Company Pattern · Aptitude",
            category="Service Company Pattern · Aptitude",
            duration_min=30,
            total_questions=30,
            sections_json={
                "Quantitative": {"completed": 12, "total": 15},
                "Logical reasoning": {"completed": 0, "total": 10},
                "Verbal ability": {"completed": 0, "total": 5}
            }
        )
        db.add(test)
        db.flush()
        
        # 30 Questions with Question 12 matching PDF 4 exactly
        for q_num in range(1, 31):
            if q_num == 12:
                q = PracticeQuestion(
                    id=f"q_{q_num}",
                    college_id="col_demo_001",
                    test_id="test_service_aptitude",
                    question_number=12,
                    section_name="Quantitative",
                    topic="Time & Work",
                    question_text="A can complete a piece of work in 12 days, and B can complete the same work in 20 days. If both of them work together for 3 days, and then A leaves, in how many more days will B finish the remaining work alone?",
                    option_a="6 days",
                    option_b="7.5 days",
                    option_c="8 days",
                    option_d="9 days",
                    correct_option="B",
                    explanation="A's 1 day work = 1/12, B's 1 day work = 1/20. Together in 1 day = (5+3)/60 = 8/60. In 3 days = 24/60 = 2/5. Remaining work = 3/5. Time for B = (3/5) / (1/20) = 12 days."
                )
            else:
                q = PracticeQuestion(
                    id=f"q_{q_num}",
                    college_id="col_demo_001",
                    test_id="test_service_aptitude",
                    question_number=q_num,
                    section_name="Quantitative" if q_num <= 15 else ("Logical reasoning" if q_num <= 25 else "Verbal ability"),
                    topic="Aptitude & Logic",
                    question_text=f"Sample Question {q_num}: Evaluate the logical pattern or arithmetic sequence to determine the correct target parameter.",
                    option_a="14",
                    option_b="28",
                    option_c="42",
                    option_d="56",
                    correct_option="A"
                )
            db.add(q)
            
        # Demo active attempt matching PDF 4 mockup state
        now = datetime.datetime.utcnow()
        demo_attempt = TestAttempt(
            id="att_demo_priya",
            college_id="col_demo_001",
            test_id="test_service_aptitude",
            student_id="std_priya_01",
            status="in_progress",
            started_at=now - datetime.timedelta(minutes=11, seconds=18),
            ends_at=now + datetime.timedelta(seconds=1122), # 18:42 remaining
            total_questions=30
        )
        db.add(demo_attempt)
        db.flush()

        for qn in range(1, 13):
            ans = AttemptAnswer(
                id=f"ans_demo_{qn}",
                college_id="col_demo_001",
                attempt_id="att_demo_priya",
                question_id=f"q_{qn}",
                question_number=qn,
                selected_option="B" if qn == 12 else "A",
                is_marked_for_review=(qn in [7, 14]),
                saved_at=now
            )
            db.add(ans)

        ans14 = AttemptAnswer(
            id="ans_demo_14",
            college_id="col_demo_001",
            attempt_id="att_demo_priya",
            question_id="q_14",
            question_number=14,
            selected_option=None,
            is_marked_for_review=True,
            saved_at=now
        )
        db.add(ans14)
            
        # 6. Virtual Labs (Screen 29 - PDF 5)
        labs = [
            VirtualLabItem(
                id="lab_linux",
                college_id="col_demo_001",
                name="Linux Sandbox",
                category="Software Engineering",
                description="Full Ubuntu terminal for commands, scripting and permissions practice.",
                eligibility_chip="Sem 2+",
                status_chip="Ready",
                tag_color="green",
                footer_text="Session: 2 hrs",
                requires_approval=False
            ),
            VirtualLabItem(
                id="lab_docker_k8s",
                college_id="col_demo_001",
                name="Docker & Kubernetes Lab",
                category="Cloud & DevOps",
                description="Build images, run containers and deploy to a practice cluster.",
                eligibility_chip="Sem 5+",
                status_chip="Ready",
                tag_color="green",
                footer_text="Last used: yesterday",
                requires_approval=False
            ),
            VirtualLabItem(
                id="lab_cloud",
                college_id="col_demo_001",
                name="Cloud Sandbox",
                category="Cloud & DevOps",
                description="Education-tier cloud account to launch VMs, storage and deploy apps.",
                eligibility_chip="Sem 5+",
                status_chip="Credits: 68%",
                tag_color="amber",
                footer_text="Auto-stops idle resources",
                requires_approval=False
            ),
            VirtualLabItem(
                id="lab_ai_notebook",
                college_id="col_demo_001",
                name="AI Notebook Lab",
                category="AI & Data Science",
                description="Notebooks with high-performance compute for ML, deep learning and RAG.",
                eligibility_chip="AI & DS",
                status_chip="Ready",
                tag_color="purple",
                footer_text="Queue: none",
                requires_approval=False,
                is_active_session=True,
                active_filename="rag_notes_demo.ipynb",
                active_minutes=38
            ),
            VirtualLabItem(
                id="lab_cyber_range",
                college_id="col_demo_001",
                name="Cyber Range",
                category="Cybersecurity",
                description="Isolated network with vulnerable targets for legal, safe security practice.",
                eligibility_chip="Cybersecurity",
                status_chip="Track access",
                tag_color="red",
                footer_text="Trainer approval needed",
                requires_approval=True
            ),
            VirtualLabItem(
                id="lab_fullstack",
                college_id="col_demo_001",
                name="Full-Stack Workspace",
                category="Software Engineering",
                description="Browser IDE with Node, Java, Python and databases pre-configured.",
                eligibility_chip="Sem 3+",
                status_chip="Ready",
                tag_color="green",
                footer_text="Linked to your GitHub",
                requires_approval=False
            ),
        ]
        db.add_all(labs)
        
        # 7. Sprint Board (Screen 30 - PDF 6)
        tasks = [
            SprintTask(id="task_01", college_id="col_demo_001", title="SMS reminder for appointments (CR-04)", tag="Feature", tag_type="feature", column_name="todo", assignee_initials="KS", assignee_name="Karthik S", story_points=5),
            SprintTask(id="task_02", college_id="col_demo_001", title="Doctor availability calendar", tag="Feature", tag_type="feature", column_name="todo", assignee_initials="MV", assignee_name="Meena V", story_points=3),
            SprintTask(id="task_03", college_id="col_demo_001", title="Accessibility review", tag="QA", tag_type="qa", column_name="todo", assignee_initials="AN", assignee_name="Ananya P", story_points=2),
            SprintTask(id="task_04", college_id="col_demo_001", title="AI symptom triage (LLM API)", tag="AI feature", tag_type="ai", column_name="in_progress", assignee_initials="PR", assignee_name="Priya R", story_points=8),
            SprintTask(id="task_05", college_id="col_demo_001", title="Patient history API", tag="Backend", tag_type="backend", column_name="in_progress", assignee_initials="RD", assignee_name="Rahul D", story_points=5),
            SprintTask(id="task_06", college_id="col_demo_001", title="Booking UI – mobile layout", tag="Frontend", tag_type="frontend", column_name="in_progress", assignee_initials="KS", assignee_name="Karthik S", story_points=3),
            SprintTask(id="task_07", college_id="col_demo_001", title="JWT refresh tokens PR #41", tag="Backend", tag_type="backend", column_name="code_review", assignee_initials="RD", assignee_name="Rahul D", story_points=3, pr_number="#41"),
            SprintTask(id="task_08", college_id="col_demo_001", title="Unit tests – booking service PR #39", tag="QA", tag_type="qa", column_name="code_review", assignee_initials="PR", assignee_name="Priya R", story_points=3, pr_number="#39"),
            SprintTask(id="task_09", college_id="col_demo_001", title="Login & roles", tag="Feature", tag_type="feature", column_name="done", assignee_initials="PR", assignee_name="Priya R", story_points=5),
            SprintTask(id="task_10", college_id="col_demo_001", title="Appointment CRUD", tag="Backend", tag_type="backend", column_name="done", assignee_initials="RD", assignee_name="Rahul D", story_points=5),
            SprintTask(id="task_11", college_id="col_demo_001", title="CI/CD pipeline", tag="DevOps", tag_type="devops", column_name="done", assignee_initials="MV", assignee_name="Meena V", story_points=5),
            SprintTask(id="task_12", college_id="col_demo_001", title="Database migrations & schema", tag="Backend", tag_type="backend", column_name="done", assignee_initials="AN", assignee_name="Ananya P", story_points=3)
        ]
        db.add_all(tasks)
        
        # 8. Mock Interviews (Screen 36 - PDF 7)
        interview = MockInterview(
            id="mock_02",
            college_id="col_demo_001",
            student_id="std_priya_01",
            round_title="Mock Interview #2 – Technical",
            interview_date="Oct 8 · 40 min",
            interviewer_name="Arun K.",
            overall_score=3.8,
            service_chip="Hire-ready for service roles",
            product_chip="Improve for product roles",
            problem_solving=4,
            coding_correctness=4,
            thinking_aloud=3,
            core_cs=4,
            project_explanation=4,
            communication=3,
            feedback_text="Strong grasp of graph traversals and Union-Find. Identified edge cases quickly and wrote clean Python code. When asked about time complexity, spent some time deriving it rather than stating it immediately. Recommend practicing thinking aloud and expressing Big-O notation with confidence.",
            recording_url="/videos/mock_interview_priya_02.mp4"
        )
        db.add(interview)
        
        # 9. Discussion Groups (Screen 34 - PDF 11)
        groups = [
            DiscussionGroup(id="grp_batch", college_id="col_demo_001", name="AI & DS · Sem 5 Batch", unread_badge=3, members_count=42, online_count=18),
            DiscussionGroup(id="grp_doubts", college_id="col_demo_001", name="Track Doubts · ML", unread_badge=5, members_count=42, online_count=18, pinned_note="Post code as snippets, never share answers to graded tests. Be respectful."),
            DiscussionGroup(id="grp_dsa", college_id="col_demo_001", name="DSA Daily Problem", unread_badge=0, members_count=56, online_count=22),
            DiscussionGroup(id="grp_team", college_id="col_demo_001", name="Team: Crop Price Predictor", unread_badge=2, members_count=3, online_count=3),
            DiscussionGroup(id="grp_placement", college_id="col_demo_001", name="Placement Updates", unread_badge=1, is_locked_announcement=True, members_count=180, online_count=45),
            DiscussionGroup(id="grp_gd", college_id="col_demo_001", name="GD & Communication", unread_badge=0, members_count=35, online_count=12)
        ]
        db.add_all(groups)
        
        group_messages = [
            GroupMessage(
                id="msg_01",
                college_id="col_demo_001",
                group_id="grp_doubts",
                sender_name="Sneha N",
                sender_role="Student",
                sender_initials="SN",
                message_text="I'm getting 0.97 cross-validation score on the training set, but test accuracy drops to 0.64. I standardized features before splitting. Could that cause it?",
                code_snippet="from sklearn.preprocessing import StandardScaler\nscaler = StandardScaler()\nX_scaled = scaler.fit_transform(X) # before train_test_split",
                timestamp_str="10:24 AM"
            ),
            GroupMessage(
                id="msg_02",
                college_id="col_demo_001",
                group_id="grp_doubts",
                sender_name="Vikram R",
                sender_role="Student",
                sender_initials="VR",
                message_text="Yes! That is classic data leakage. The scaler learned the mean and variance of your test set during fit_transform.",
                timestamp_str="10:28 AM"
            ),
            GroupMessage(
                id="msg_03",
                college_id="col_demo_001",
                group_id="grp_doubts",
                sender_name="Arun K.",
                sender_role="Trainer",
                sender_initials="AK",
                message_text="Spot on Vikram. Always fit the scaler only on the training fold, or wrap the model inside a scikit-learn Pipeline so it handles this automatically in cross-validation.",
                is_marked_as_answer=True,
                reactions_count=12,
                timestamp_str="10:35 AM"
            )
        ]
        db.add_all(group_messages)
        
        # 10. Trainer Message Hub (Screen 35 - PDF 12)
        threads = [
            TrainerDirectThread(id="th_ramesh", college_id="col_demo_001", trainer_user_id="usr_arun_01", contact_name="Mr. Ramesh K", contact_category="Parents", contact_role_chip="Parent · Priya R", avatar_initials="RK", pref_language="Prefers Tamil", unread_badge=0, last_message_preview="Vanakkam sir, Priya's mock interview feedback received. Nandri.", last_message_time="10:45 AM"),
            TrainerDirectThread(id="th_lakshmi", college_id="col_demo_001", trainer_user_id="usr_arun_01", contact_name="Mrs. Lakshmi S", contact_category="Parents", contact_role_chip="Parent · Karthik S", avatar_initials="LS", pref_language="Prefers English", unread_badge=2, last_message_preview="Will Karthik have extra coaching this Saturday?", last_message_time="Yesterday"),
            TrainerDirectThread(id="th_kavitha", college_id="col_demo_001", trainer_user_id="usr_arun_01", contact_name="Dr. Kavitha (Coordinator)", contact_category="College", contact_role_chip="College Coordinator", avatar_initials="DK", pref_language="Prefers English", unread_badge=1, last_message_preview="MoU progress report due for the governing council review.", last_message_time="Yesterday"),
            TrainerDirectThread(id="th_placement", college_id="col_demo_001", trainer_user_id="usr_arun_01", contact_name="Placement Cell", contact_category="College", contact_role_chip="Placement Officer", avatar_initials="PC", pref_language="Prefers English", unread_badge=0, last_message_preview="Shortlisted candidates for Mock Drive 1 ready.", last_message_time="Oct 7")
        ]
        db.add_all(threads)
        
        direct_msgs = [
            DirectMessage(id="dm_01", college_id="col_demo_001", thread_id="th_ramesh", is_incoming=True, sender_name="Mr. Ramesh K", text_en="Hello Arun sir, I reviewed Priya's October progress card. Her coding score improved nicely.", text_ta="வணக்கம் அருண் சார், பிரியாவின் அக்டோபர் மாத முன்னேற்ற அட்டையைப் பார்த்தேன். கோடிங் மதிப்பெண்கள் நன்றாக உயர்ந்துள்ளது.", timestamp_str="10:30 AM"),
            DirectMessage(id="dm_02", college_id="col_demo_001", thread_id="th_ramesh", is_incoming=False, sender_name="Arun Kumar", text_en="Hello Mr. Ramesh! Yes, Priya solved 34 problems this month. If she practices spoken English for 10 minutes daily at home, she will easily reach the Placement Ready band.", text_ta="வணக்கம் ரமேஷ் சார்! ஆம், பிரியா இந்த மாதம் 34 கணக்குகளைத் தீர்த்துள்ளார். வீட்டில் தினமும் 10 நிமிடங்கள் ஆங்கிலத்தில் பேச பயிற்சி செய்தால் பிளேஸ்மென்ட் தயார் நிலையை எளிதில் எட்டிவிடுவார்.", timestamp_str="10:38 AM"),
            DirectMessage(id="dm_03", college_id="col_demo_001", thread_id="th_ramesh", is_incoming=True, sender_name="Mr. Ramesh K", text_en="Sure sir, we will definitely encourage her. Thank you for your guidance.", text_ta="நிச்சயமாக சார், நாங்கள் அவளை ஊக்குவிக்கிறோம். உங்கள் வழிகாட்டுதலுக்கு நன்றி.", timestamp_str="10:45 AM")
        ]
        db.add_all(direct_msgs)
        
        # 11. Sessions & Schedule (Screen 08 & 13 - PDF 8, 14)
        now = datetime.datetime.utcnow()
        sessions_list = [
            SessionItem(
                id="sess_thu_rag",
                college_id="col_demo_001",
                title="Future Skills: LLM APIs & RAG",
                track="AI & DS",
                trainer_name="Arun K.",
                scheduled_start=now.replace(hour=11, minute=0, second=0, microsecond=0),
                scheduled_end=now.replace(hour=12, minute=0, second=0, microsecond=0),
                duration_min=60,
                session_type="Live",
                status="Upcoming",
                has_lab_preload=True,
                lab_name="AI Notebook pre-loaded"
            ),
            SessionItem(
                id="sess_mon_unionfind",
                college_id="col_demo_001",
                title="DSA: Union-Find drill",
                track="CSE & AI",
                trainer_name="Arun K.",
                scheduled_start=now - datetime.timedelta(days=3),
                scheduled_end=now - datetime.timedelta(days=3) + datetime.timedelta(hours=1),
                duration_min=60,
                session_type="Live",
                status="Attended",
                recording_url="/recordings/dsa_union_find.mp4",
                recording_duration="58 min"
            ),
            SessionItem(
                id="sess_tue_model_eval",
                college_id="col_demo_001",
                title="Track: Model evaluation lab",
                track="AI & DS",
                trainer_name="Arun K.",
                scheduled_start=now - datetime.timedelta(days=2),
                scheduled_end=now - datetime.timedelta(days=2) + datetime.timedelta(hours=1),
                duration_min=60,
                session_type="Live",
                status="Attended",
                recording_url="/recordings/model_eval.mp4",
                recording_duration="1 hr 2 min"
            ),
            SessionItem(
                id="sess_wed_aptitude",
                college_id="col_demo_001",
                title="Aptitude: Data interpretation",
                track="General",
                trainer_name="Pooja M.",
                scheduled_start=now - datetime.timedelta(days=1),
                scheduled_end=now - datetime.timedelta(days=1) + datetime.timedelta(hours=1),
                duration_min=60,
                session_type="Live",
                status="Missed",
                recording_url="/recordings/data_interpretation.mp4",
                recording_duration="54 min"
            ),
            SessionItem(
                id="sess_fri_quiz",
                college_id="col_demo_001",
                title="GD + weekly quiz",
                track="Communication",
                trainer_name="Siddharth R.",
                scheduled_start=now + datetime.timedelta(days=1),
                scheduled_end=now + datetime.timedelta(days=1) + datetime.timedelta(hours=1),
                duration_min=60,
                session_type="Live",
                status="Scheduled"
            ),
            SessionItem(
                id="sess_sat_track_project",
                college_id="col_demo_001",
                title="Track project kick-off + RAG mini-lab",
                track="AI & DS",
                trainer_name="Arun K.",
                scheduled_start=now + datetime.timedelta(days=2),
                scheduled_end=now + datetime.timedelta(days=2) + datetime.timedelta(hours=3),
                duration_min=180,
                session_type="In-lab / Hybrid",
                status="Scheduled"
            )
        ]
        db.add_all(sessions_list)
        
        # 12. Parent Monthly Progress Card (Screen 15 - PDF 10)
        parent_cards = [
            ParentMonthlyRecord(id="pmr_01", college_id="col_demo_001", student_id="std_priya_01", month_name="October", area="Coding (problems solved)", prev_month_val="252", curr_month_val="286", status_text="On track", status_color="green"),
            ParentMonthlyRecord(id="pmr_02", college_id="col_demo_001", student_id="std_priya_01", month_name="October", area="Aptitude test", prev_month_val="64%", curr_month_val="71%", status_text="Improving", status_color="green"),
            ParentMonthlyRecord(id="pmr_03", college_id="col_demo_001", student_id="std_priya_01", month_name="October", area="Project", prev_month_val="Planning", curr_month_val="45% built", status_text="On track", status_color="green"),
            ParentMonthlyRecord(id="pmr_04", college_id="col_demo_001", student_id="std_priya_01", month_name="October", area="Communication", prev_month_val="3/5", curr_month_val="3/5", status_text="Needs practice", status_color="amber")
        ]
        db.add_all(parent_cards)
        
        db.commit()
        print("Database seeded successfully with all mockup data.", flush=True)
    finally:
        db.close()

if __name__ == "__main__":
    init_db_and_seed()
