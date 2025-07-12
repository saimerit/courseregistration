import streamlit as st
import pandas as pd
import sqlite3
import os
import datetime # Import datetime for generating ClassID
import time # Import time for delays in retry mechanism

# --- Constants for SQLite Database File ---
DB_FILE = 'course_registration.db'

# --- Helper Functions for Data Handling (SQLite) ---

def init_db():
    """Initializes the SQLite database and creates tables if they don't exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create Passwords table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS passwords (
            UserID TEXT PRIMARY KEY,
            Password TEXT NOT NULL,
            Role TEXT NOT NULL
        )
    ''')

    # Create Students table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            StudentID TEXT PRIMARY KEY,
            StudentName TEXT NOT NULL,
            Password TEXT NOT NULL
        )
    ''')

    # Create Faculty table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS faculty (
            FacultyID TEXT PRIMARY KEY,
            FacultyName TEXT NOT NULL,
            Password TEXT NOT NULL
        )
    ''')

    # Create Courses table (Capacity and EnrolledStudents moved to course_faculty_assignments)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS courses (
            CourseID TEXT PRIMARY KEY,
            CourseName TEXT NOT NULL,
            Credits INTEGER NOT NULL
        )
    ''')

    # Create Course-Faculty Assignments table (Junction Table for Many-to-Many)
    # Now includes ClassID as primary key for each assignment
    # Capacity and EnrolledStudents are now per faculty assignment
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS course_faculty_assignments (
            ClassID TEXT PRIMARY KEY, -- This ClassID identifies a specific faculty-course assignment
            CourseID TEXT NOT NULL,
            FacultyID TEXT NOT NULL, 
            Capacity INTEGER NOT NULL,       -- Capacity for this specific offering
            EnrolledStudents INTEGER DEFAULT 0, -- Enrolled students for this specific offering
            FOREIGN KEY (CourseID) REFERENCES courses(CourseID) ON DELETE CASCADE,
            FOREIGN KEY (FacultyID) REFERENCES faculty(FacultyID) ON DELETE CASCADE
        )
    ''')

    # Create Enrollments table
    # Changed to link to FacultyAssignmentClassID (from course_faculty_assignments)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS enrollments (
            ClassID TEXT PRIMARY KEY, -- This is the student's enrollment ClassID
            StudentID TEXT NOT NULL,
            FacultyAssignmentClassID TEXT NOT NULL, -- Links to course_faculty_assignments.ClassID
            FOREIGN KEY (StudentID) REFERENCES students(StudentID) ON DELETE CASCADE,
            FOREIGN KEY (FacultyAssignmentClassID) REFERENCES course_faculty_assignments(ClassID) ON DELETE CASCADE
        )
    ''')
    
    # Create a sequences table to manage auto-generated IDs
    # This sequence will be used globally for both enrollment ClassIDs and faculty assignment ClassIDs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sequences (
            name TEXT PRIMARY KEY,
            value INTEGER NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Initialize the database when the script starts
init_db()

def get_next_sequence_number(sequence_name='global_class_id_sequence', conn=None, cursor=None):
    """
    Retrieves and increments a sequence number from the 'sequences' table.
    Initializes the sequence if it doesn't exist.
    This sequence is global to ensure unique ClassIDs across all tables using them.
    Can use an existing connection/cursor or open a new one.
    """
    if conn is None or cursor is None:
        local_conn = sqlite3.connect(DB_FILE)
        local_cursor = local_conn.cursor()
    else:
        local_conn = conn
        local_cursor = cursor

    try:
        # Insert with IGNORE to avoid error if already exists, then update
        # Initial value for ClassID sequence is 100000, so the first generated ID is 100001
        local_cursor.execute("INSERT OR IGNORE INTO sequences (name, value) VALUES (?, ?)", (sequence_name, 100000)) 
        
        local_cursor.execute("SELECT value FROM sequences WHERE name = ?", (sequence_name,))
        current_value = local_cursor.fetchone()[0]
        
        new_value = current_value + 1
        local_cursor.execute("UPDATE sequences SET value = ? WHERE name = ?", (new_value, sequence_name))
        
        # Only commit if a new local connection was opened
        if conn is None:
            local_conn.commit()
        return new_value
    finally:
        # Only close if a new local connection was opened
        if conn is None:
            local_conn.close()

def generate_class_id(conn=None, cursor=None):
    """
    Generates a unique ClassID in the format BL<CurrentYear><NextYearLastTwoDigits><SequenceNumber>.
    This ID is unique globally across student enrollments and faculty assignments.
    Example: BL202425100001
    Can use an existing connection/cursor or open a new one.
    """
    current_year = datetime.datetime.now().year
    next_year_last_two_digits = (current_year + 1) % 100
    
    # Get the next global sequence number, passing the connection/cursor
    sequence_number = get_next_sequence_number('global_class_id_sequence', conn, cursor)
    
    # Format the ClassID string
    return f"BL{current_year}{next_year_last_two_digits:02d}{sequence_number:06d}"


def load_table_to_df(table_name, columns):
    """Loads data from a SQLite table into a pandas DataFrame."""
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        # Ensure all required columns are present, add them if missing
        for col in columns:
            if col not in df.columns:
                df[col] = None
        
        # Explicitly convert 'Capacity' and 'EnrolledStudents' to numeric, coercing errors
        if 'Capacity' in df.columns:
            df['Capacity'] = pd.to_numeric(df['Capacity'], errors='coerce').fillna(0).astype(int)
        if 'EnrolledStudents' in df.columns:
            df['EnrolledStudents'] = pd.to_numeric(df['EnrolledStudents'], errors='coerce').fillna(0).astype(int)

        return df[columns] # Return only the required columns
    except Exception as e:
        st.error(f"Error loading data from SQLite table '{table_name}': {e}")
        return pd.DataFrame(columns=columns)
    finally:
        conn.close()

def execute_query(query, params=(), retries=5, delay=0.1):
    """
    Executes a SQL query with optional parameters, including retry logic for database locks.
    This function is primarily for single-statement operations or when a new transaction is desired.
    For multi-statement transactions, manage connection/cursor explicitly.
    """
    for i in range(retries):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            conn.commit()
            return True
        except sqlite3.OperationalError as e:
            # Corrected syntax error: removed '\n'
            if "database is locked" in str(e) and i < retries - 1:
                st.warning(f"Database is locked. Retrying in {delay} seconds... (Attempt {i+1}/{retries})")
                time.sleep(delay)
                delay *= 2 # Exponential backoff
            else:
                st.error(f"Database error: {e}")
                return False
        except sqlite3.Error as e:
            st.error(f"Database error: {e}")
            return False
        finally:
            conn.close()
    return False # All retries failed

def get_row_by_id(table_name, id_column, row_id):
    """Retrieves a single row by its ID from a SQLite table."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT * FROM {table_name} WHERE {id_column} = ?", (row_id,))
        row = cursor.fetchone()
        if row:
            # Get column names from cursor description
            cols = [description[0] for description in cursor.description]
            return dict(zip(cols, row))
        return None
    except Exception as e:
        st.error(f"Error getting row '{row_id}' from '{table_name}': {e}")
        return None
    finally:
        conn.close()

# --- Authentication Functions (Adapted for SQLite) ---

def authenticate_admin_misc(user_id, password):
    """Authenticates an admin user against SQLite."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM passwords WHERE UserID = ? AND Password = ? AND Role = 'admin'", (user_id, password))
    user_row = cursor.fetchone()
    conn.close()
    return user_row is not None

def authenticate_faculty_student(user_id, password, role):
    """Authenticates a faculty or student user against SQLite."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # First, check against the passwords table
    cursor.execute("SELECT * FROM passwords WHERE UserID = ? AND Password = ? AND Role = ?", (user_id, password, role))
    password_match = cursor.fetchone()
    
    if not password_match:
        conn.close()
        return False

    # Additionally verify their existence in their respective table
    if role == 'faculty':
        cursor.execute("SELECT * FROM faculty WHERE FacultyID = ?", (user_id,))
        user_exists = cursor.fetchone()
    elif role == 'student':
        cursor.execute("SELECT * FROM students WHERE StudentID = ?", (user_id,))
        user_exists = cursor.fetchone()
    else:
        user_exists = None # Should not happen with valid roles

    conn.close()
    return user_exists is not None

# --- User Classes (Adapted for Streamlit and SQLite) ---

class Admin:
    """Manages administrative tasks."""
    def __init__(self):
        pass

    def add_new_faculty(self):
        """Adds a new faculty member."""
        st.subheader("Add New Faculty")
        with st.form("add_faculty_form"):
            faculty_id = st.text_input("Faculty ID (e.g., F001)").strip().upper()
            faculty_name = st.text_input("Faculty Name").strip()
            password = st.text_input("Password", type="password").strip()
            submitted = st.form_submit_button("Add Faculty")

            if submitted:
                if not faculty_id or not faculty_name or not password:
                    st.error("All fields are required.")
                    return

                # Check if Faculty ID exists
                if get_row_by_id('faculty', 'FacultyID', faculty_id):
                    st.error(f"Faculty ID '{faculty_id}' already exists.")
                    return
                
                # Check if User ID exists in passwords table
                if get_row_by_id('passwords', 'UserID', faculty_id):
                    st.error(f"User ID '{faculty_id}' already exists in passwords (potentially as student/admin).")
                    return

                # Add to faculty table
                if execute_query("INSERT INTO faculty (FacultyID, FacultyName, Password) VALUES (?, ?, ?)", (faculty_id, faculty_name, password)):
                    # Add to passwords table
                    if execute_query("INSERT INTO passwords (UserID, Password, Role) VALUES (?, ?, ?)", (faculty_id, password, 'faculty')):
                        st.success(f"Faculty '{faculty_name}' (ID: {faculty_id}) added successfully.")
                        st.session_state.faculty_data_updated = True # Trigger a refresh if needed
                    else:
                        st.error("Failed to add faculty password. Please try again.")
                        # Consider rolling back faculty addition if password fails
                        execute_query("DELETE FROM faculty WHERE FacultyID = ?", (faculty_id,))
                else:
                    st.error("Failed to add faculty. Please try again.")

    def add_new_student(self):
        """Adds a new student."""
        st.subheader("Add New Student")
        with st.form("add_student_form"):
            student_id = st.text_input("Student ID (e.g., S001)").strip().upper()
            student_name = st.text_input("Student Name").strip()
            password = st.text_input("Password", type="password").strip()
            submitted = st.form_submit_button("Add Student")

            if submitted:
                if not student_id or not student_name or not password:
                    st.error("All fields are required.")
                    return

                # Check if Student ID exists
                if get_row_by_id('students', 'StudentID', student_id):
                    st.error(f"Student ID '{student_id}' already exists.")
                    return
                
                # Check if User ID exists in passwords table
                if get_row_by_id('passwords', 'UserID', student_id):
                    st.error(f"User ID '{student_id}' already exists in passwords (potentially as faculty/admin).")
                    return

                # Add to students table
                if execute_query("INSERT INTO students (StudentID, StudentName, Password) VALUES (?, ?, ?)", (student_id, student_name, password)):
                    # Add to passwords table
                    if execute_query("INSERT INTO passwords (UserID, Password, Role) VALUES (?, ?, ?)", (student_id, password, 'student')):
                        st.success(f"Student '{student_name}' (ID: {student_id}) added successfully.")
                        st.session_state.student_data_updated = True # Trigger a refresh if needed
                    else:
                        st.error("Failed to add student password. Please try again.")
                        # Consider rolling back student addition if password fails
                        execute_query("DELETE FROM students WHERE StudentID = ?", (student_id,))
                else:
                    st.error("Failed to add student. Please try again.")

    def modify_faculty(self):
        """Allows admin to modify existing faculty details."""
        st.subheader("Modify Existing Faculty")
        faculty_df = load_table_to_df('faculty', ['FacultyID', 'FacultyName', 'Password'])
        
        if faculty_df.empty:
            st.info("No faculty members to modify.")
            return

        selected_faculty_id = st.selectbox(
            "Select Faculty to Modify",
            options=[""] + faculty_df['FacultyID'].tolist(),
            key="modify_faculty_select"
        )

        if selected_faculty_id:
            faculty_row = get_row_by_id('faculty', 'FacultyID', selected_faculty_id)
            if not faculty_row:
                st.error("Selected faculty not found.")
                return
            
            st.write(f"Modifying Faculty: {faculty_row.get('FacultyName')} ({selected_faculty_id})")
            with st.form("modify_faculty_form"):
                new_faculty_name = st.text_input("New Faculty Name", value=faculty_row.get('FacultyName')).strip()
                # Corrected the missing closing quote for type="password"
                new_password = st.text_input("New Password", value=faculty_row.get('Password'), type="password").strip()
                submitted = st.form_submit_button("Update Faculty")

                if submitted:
                    if not new_faculty_name or not new_password:
                        st.error("All fields are required.")
                        return
                    
                    # Update faculty table
                    if execute_query(
                        "UPDATE faculty SET FacultyName = ?, Password = ? WHERE FacultyID = ?",
                        (new_faculty_name, new_password, selected_faculty_id)
                    ):
                        # Update passwords table
                        if execute_query(
                            "UPDATE passwords SET Password = ? WHERE UserID = ?",
                            (new_password, selected_faculty_id)
                        ):
                            st.success(f"Faculty '{selected_faculty_id}' updated successfully.")
                            st.session_state.faculty_data_updated = True
                        else:
                            st.error("Failed to update faculty password. Please try again.")
                    else:
                        st.error("Failed to update faculty details. Please try again.")
        else:
            st.info("Select a faculty member to modify.")

    def modify_student(self):
        """Allows admin to modify existing student details."""
        st.subheader("Modify Existing Student")
        students_df = load_table_to_df('students', ['StudentID', 'StudentName', 'Password'])
        
        if students_df.empty:
            st.info("No students to modify.")
            return

        selected_student_id = st.selectbox(
            "Select Student to Modify",
            options=[""] + students_df['StudentID'].tolist(),
            key="modify_student_select"
        )

        if selected_student_id:
            student_row = get_row_by_id('students', 'StudentID', selected_student_id)
            if not student_row:
                st.error("Selected student not found.")
                return
            
            st.write(f"Modifying Student: {student_row.get('StudentName')} ({selected_student_id})")
            with st.form("modify_student_form"):
                new_student_name = st.text_input("New Student Name", value=student_row.get('StudentName')).strip()
                # Corrected the missing closing quote for type="password"
                new_password = st.text_input("New Password", value=student_row.get('Password'), type="password").strip()
                submitted = st.form_submit_button("Update Student")

                if submitted:
                    if not new_student_name or not new_password:
                        st.error("All fields are required.")
                        return
                    
                    # Update students table
                    if execute_query(
                        "UPDATE students SET StudentName = ?, Password = ? WHERE StudentID = ?",
                        (new_student_name, new_password, selected_student_id)
                    ):
                        # Update passwords table
                        if execute_query(
                            "UPDATE passwords SET Password = ? WHERE UserID = ?",
                            (new_password, selected_student_id)
                        ):
                            st.success(f"Student '{selected_student_id}' updated successfully.")
                            st.session_state.student_data_updated = True
                        else:
                            st.error("Failed to update student password. Please try again.")
                    else:
                        st.error("Failed to update student details. Please try again.")
        else:
            st.info("Select a student to modify.")


    def create_course_assignment(self):
        """Creates a new course and assigns multiple faculty members, generating a ClassID for each assignment."""
        st.subheader("Create New Course or Add New Faculty Offering to Existing Course") # Updated subheader
        faculty_df = load_table_to_df('faculty', ['FacultyID', 'FacultyName'])
        available_faculty_ids = faculty_df['FacultyID'].tolist() if not faculty_df.empty else []

        if not available_faculty_ids:
            st.warning("No faculty members registered. Please add faculty first.")
            return

        with st.form("create_course_form"):
            course_id = st.text_input("Course ID (e.g., CS101)").strip().upper()
            course_name = st.text_input("Course Name").strip()
            credits = st.number_input("Credits", min_value=1, max_value=6, value=3)
            selected_faculty_ids = st.multiselect("Assign Faculty (select multiple)", options=available_faculty_ids)
            capacity_per_assignment = st.number_input("Capacity per Faculty Assignment", min_value=1, value=30)
            
            submitted = st.form_submit_button("Create Course & Assignments / Add New Offering") # Updated button text

            if submitted:
                if not course_id or not course_name or not selected_faculty_ids:
                    st.error("All fields are required.")
                    return

                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                try:
                    # Check if Course ID already exists in the 'courses' table
                    cursor.execute("SELECT 1 FROM courses WHERE CourseID = ?", (course_id,))
                    course_exists = cursor.fetchone()

                    if not course_exists:
                        # If the course does NOT exist, create it
                        cursor.execute(
                            "INSERT INTO courses (CourseID, CourseName, Credits) VALUES (?, ?, ?)",
                            (course_id, course_name, credits)
                        )
                        st.success(f"New Course '{course_name}' (ID: {course_id}) created.")
                    else:
                        # If the course DOES exist, inform the user or optionally update course details.
                        # For now, we'll just inform and proceed to add offerings.
                        existing_course_row = get_row_by_id('courses', 'CourseID', course_id)
                        if existing_course_row and (existing_course_row['CourseName'] != course_name or existing_course_row['Credits'] != credits):
                            st.warning(f"Course ID '{course_id}' already exists with different details. Adding new offering under existing course.")
                            # Optional: Update course details if they differ, but this might not be desired behavior
                            # cursor.execute("UPDATE courses SET CourseName = ?, Credits = ? WHERE CourseID = ?, (course_name, credits, course_id))
                        else:
                            st.info(f"Course ID '{course_id}' already exists. Adding new offering(s) to this course.")

                    # Now, insert into course_faculty_assignments for each selected faculty
                    generated_class_ids = []
                    for faculty_id in selected_faculty_ids:
                        # Check if this specific faculty-course assignment already exists
                        cursor.execute("SELECT 1 FROM course_faculty_assignments WHERE CourseID = ? AND FacultyID = ?", (course_id, faculty_id))
                        assignment_exists = cursor.fetchone()
                        if assignment_exists:
                            st.warning(f"Faculty '{faculty_id}' is already assigned to Course '{course_id}'. Skipping this assignment.")
                            continue # Skip to the next faculty if this assignment already exists

                        new_class_id = generate_class_id(conn, cursor) 
                        cursor.execute(
                            "INSERT INTO course_faculty_assignments (ClassID, CourseID, FacultyID, Capacity, EnrolledStudents) VALUES (?, ?, ?, ?, ?)",
                            (new_class_id, course_id, faculty_id, capacity_per_assignment, 0)
                        )
                        generated_class_ids.append(f"{faculty_id} ({new_class_id})")

                    conn.commit()
                    if generated_class_ids:
                        st.success(f"New Faculty Offering(s) added for Course '{course_id}': {', '.join(generated_class_ids)}")
                    else:
                        st.info("No new faculty offerings were added (they might already exist or an error occurred).")
                    st.session_state.course_data_updated = True
                except sqlite3.Error as e:
                    conn.rollback()
                    st.error(f"Failed to create course or assign faculty: {e}. Changes rolled back.")
                finally:
                    conn.close()

    def modify_course_assignment(self):
        """Modifies an existing course and its faculty assignments (offerings)."""
        st.subheader("Modify Existing Course & Faculty Offerings")
        
        # Load all assignments to allow selection of a specific offering
        conn = sqlite3.connect(DB_FILE)
        query_all_assignments = """
            SELECT 
                cfa.ClassID, cfa.CourseID, c.CourseName, cfa.FacultyID, f.FacultyName,
                cfa.Capacity, cfa.EnrolledStudents, c.Credits
            FROM course_faculty_assignments cfa
            JOIN courses c ON cfa.CourseID = c.CourseID
            JOIN faculty f ON cfa.FacultyID = f.FacultyID
            ORDER BY cfa.ClassID
        """
        all_assignments_df = pd.read_sql_query(query_all_assignments, conn)
        conn.close()

        if all_assignments_df.empty:
            st.info("No course assignments (faculty offerings) to modify.")
            return

        # Create display options for the selectbox
        all_assignments_df['Display'] = all_assignments_df.apply(
            lambda row: f"{row['CourseName']} ({row['CourseID']}) - Faculty: {row['FacultyName']} ({row['FacultyID']}) - Offering ID: {row['ClassID']}",
            axis=1
        )
        
        selected_assignment_display = st.selectbox(
            "Select Course Offering to Modify",
            options=[""] + all_assignments_df['Display'].tolist(),
            key="modify_assignment_select"
        )

        if selected_assignment_display:
            selected_assignment_class_id = selected_assignment_display.split('Offering ID: ')[1].strip()
            
            # Get the full row for the selected assignment
            assignment_row = all_assignments_df[all_assignments_df['ClassID'] == selected_assignment_class_id].iloc[0]
            
            course_id = assignment_row['CourseID']
            # Explicitly cast to int here to prevent TypeError in st.number_input's min_value
            current_enrolled_students_in_offering = int(assignment_row.get('EnrolledStudents', 0)) 

            st.write(f"Modifying Offering: {selected_assignment_display}")
            with st.form("modify_offering_form"):
                # Course details (can be modified if needed, but not directly tied to ClassID capacity)
                new_course_name = st.text_input("New Course Name (for parent course)", value=assignment_row.get('CourseName')).strip()
                # Fixed TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'
                # by providing a default value of 3 if 'Credits' is None
                new_credits = st.number_input("New Credits (for parent course)", min_value=1, max_value=6, value=int(assignment_row.get('Credits', 3)))
                
                # Capacity for this specific offering
                new_capacity_for_offering = st.number_input(
                    "New Capacity for this Offering", 
                    min_value=current_enrolled_students_in_offering, # Cannot set capacity below current enrolled students
                    value=int(assignment_row.get('Capacity'))
                )
                
                # Option to change faculty for this specific offering (reassign ClassID)
                faculty_df = load_table_to_df('faculty', ['FacultyID', 'FacultyName'])
                available_faculty_ids = faculty_df['FacultyID'].tolist()
                current_faculty_id = assignment_row['FacultyID']
                
                new_faculty_id_for_offering = st.selectbox(
                    "Change Faculty for this Offering",
                    options=[""] + available_faculty_ids,
                    index=available_faculty_ids.index(current_faculty_id) + 1 if current_faculty_id in available_faculty_ids else 0,
                    key="change_offering_faculty_select"
                )

                submitted = st.form_submit_button("Update Offering")

                if submitted:
                    if not new_course_name or not new_faculty_id_for_offering:
                        st.error("All fields are required.")
                        return
                    
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    try:
                        # Update parent course details
                        cursor.execute(
                            "UPDATE courses SET CourseName = ?, Credits = ? WHERE CourseID = ?",
                            (new_course_name, new_credits, course_id)
                        )
                        
                        # Update the specific course_faculty_assignment (offering)
                        # IMPORTANT: Explicitly include EnrolledStudents to preserve its value
                        cursor.execute(
                            "UPDATE course_faculty_assignments SET FacultyID = ?, Capacity = ?, EnrolledStudents = ? WHERE ClassID = ?",
                            (new_faculty_id_for_offering, new_capacity_for_offering, current_enrolled_students_in_offering, selected_assignment_class_id)
                        )
                        
                        conn.commit()
                        st.success(f"Offering '{selected_assignment_class_id}' updated successfully.")
                        st.session_state.course_data_updated = True
                        st.rerun() # Rerun to refresh display
                    except sqlite3.Error as e:
                        conn.rollback()
                        st.error(f"Failed to update offering: {e}. Changes rolled back.")
                    finally:
                        conn.close()
        else:
            st.info("Select a course offering to modify.")

    def delete_course_assignment(self):
        """Allows admin to delete a specific course assignment (offering) by ClassID."""
        st.subheader("Delete Course Assignment (Faculty Offering)")
        
        # Load all assignments to allow selection of a specific offering
        conn = sqlite3.connect(DB_FILE)
        query_all_assignments = """
            SELECT 
                cfa.ClassID, cfa.CourseID, c.CourseName, cfa.FacultyID, f.FacultyName,
                cfa.Capacity, cfa.EnrolledStudents
            FROM course_faculty_assignments cfa
            JOIN courses c ON cfa.CourseID = c.CourseID
            JOIN faculty f ON cfa.FacultyID = f.FacultyID
            ORDER BY cfa.ClassID
        """
        all_assignments_df = pd.read_sql_query(query_all_assignments, conn)
        conn.close()

        if all_assignments_df.empty:
            st.info("No course assignments (faculty offerings) to delete.")
            return

        # Create display options for the selectbox
        all_assignments_df['Display'] = all_assignments_df.apply(
            lambda row: f"{row['CourseName']} ({row['CourseID']}) - Faculty: {row['FacultyName']} ({row['FacultyID']}) - Offering ID: {row['ClassID']} (Enrolled: {row['EnrolledStudents']}/{row['Capacity']})",
            axis=1
        )
        
        selected_assignment_display = st.selectbox(
            "Select Course Offering to Delete",
            options=[""] + all_assignments_df['Display'].tolist(),
            key="delete_assignment_select"
        )

        if selected_assignment_display:
            selected_assignment_class_id = selected_assignment_display.split('Offering ID: ')[1].split(' ')[0]
            
            # Get the full row for the selected assignment for confirmation message
            assignment_row = all_assignments_df[all_assignments_df['ClassID'] == selected_assignment_class_id].iloc[0]

            st.warning(f"Are you sure you want to delete this course offering:")
            st.warning(f"Course: {assignment_row.get('CourseName')} ({assignment_row.get('CourseID')})")
            st.warning(f"Faculty: {assignment_row.get('FacultyName')} ({assignment_row.get('FacultyID')})")
            st.warning(f"Offering ID: {selected_assignment_class_id}")
            st.warning(f"This will also delete all student enrollments associated with this specific offering.")

            if st.button(f"Confirm Delete Offering {selected_assignment_class_id}"):
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                try:
                    # First, count enrollments for this assignment before deletion
                    cursor.execute("SELECT COUNT(*) FROM enrollments WHERE FacultyAssignmentClassID = ?", (selected_assignment_class_id,))
                    enrollments_before_delete = cursor.fetchone()[0]

                    # Deleting from course_faculty_assignments will cascade delete enrollments
                    cursor.execute("DELETE FROM course_faculty_assignments WHERE ClassID = ?", (selected_assignment_class_id,))
                    
                    conn.commit()

                    # After commit, re-count enrollments to confirm cascade
                    cursor.execute("SELECT COUNT(*) FROM enrollments WHERE FacultyAssignmentClassID = ?", (selected_assignment_class_id,))
                    enrollments_after_delete = cursor.fetchone()[0]

                    if enrollments_after_delete == 0:
                        st.success(f"Course offering '{selected_assignment_class_id}' and its associated student enrollments deleted successfully.")
                        if enrollments_before_delete > 0:
                            st.info(f"Confirmed: {enrollments_before_delete} student enrollment(s) were also removed due to cascade deletion.")
                    else:
                        st.error(f"Course offering '{selected_assignment_class_id}' deleted, but {enrollments_after_delete} associated student enrollments still remain. This indicates an issue with cascade deletion.")
                        st.warning("Please ensure your 'course_registration.db' file is deleted and the application is restarted to re-initialize the database with proper foreign key constraints.")

                    st.session_state.course_data_updated = True
                    st.session_state.enrollment_data_updated = True
                    st.rerun() # Rerun to refresh display
                except sqlite3.Error as e:
                    conn.rollback()
                    st.error(f"Error deleting course offering: {e}. Changes have been rolled back.")
                finally:
                    conn.close()
        else:
            st.info("Select a course offering to delete.")


    def modify_class_id_sequence(self):
        """Allows admin to change the global ClassID sequence number."""
        st.subheader("Modify Global Class ID Sequence Number")
        st.info("This allows you to set the starting point for the next generated ClassID sequence number (for both enrollments and faculty assignments). Use with caution.")
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            # Ensure the global sequence exists
            cursor.execute("INSERT OR IGNORE INTO sequences (name, value) VALUES (?, ?)", ('global_class_id_sequence', 100000))
            cursor.execute("SELECT value FROM sequences WHERE name = ?", ('global_class_id_sequence',))
            current_seq_value = cursor.fetchone()[0]
        except sqlite3.Error as e:
            st.error(f"Error reading sequence value: {e}")
            current_seq_value = 100000 # Fallback
        finally:
            conn.close()


        new_seq_value = st.number_input(
            "Set Next Sequence Number (e.g., 100000 for BL202425100001)",
            min_value=0,
            value=current_seq_value,
            step=1,
            key="new_class_id_seq"
        )
        
        if st.button("Update Class ID Sequence"):
            # This operation can use execute_query as it's a single statement
            if execute_query("UPDATE sequences SET value = ? WHERE name = ?", (new_seq_value, 'global_class_id_sequence')):
                st.success(f"Global Class ID sequence updated to start from {new_seq_value + 1}.")
            else:
                st.error("Failed to update Class ID sequence.")


    def manage_enrollments(self):
        """Manages student enrollments in specific course offerings."""
        st.subheader("Manage Student Enrollments")
        students_df = load_table_to_df('students', ['StudentID', 'StudentName'])
        courses_df = load_table_to_df('courses', ['CourseID', 'CourseName', 'Credits']) # No capacity/enrolled here
        faculty_df = load_table_to_df('faculty', ['FacultyID', 'FacultyName'])
        
        # Load course_faculty_assignments with their capacity and enrolled students
        course_faculty_assignments_df = load_table_to_df(
            'course_faculty_assignments', 
            ['ClassID', 'CourseID', 'FacultyID', 'Capacity', 'EnrolledStudents']
        )
        enrollments_df = load_table_to_df('enrollments', ['ClassID', 'StudentID', 'FacultyAssignmentClassID'])

        if students_df.empty or courses_df.empty or course_faculty_assignments_df.empty:
            st.info("No students, courses, or faculty assignments available to manage enrollments.")
            return

        student_ids = students_df['StudentID'].tolist()
        course_ids_for_filter = [""] + courses_df['CourseID'].tolist()

        st.markdown("---")
        st.subheader("Enroll/Drop Student in Offering")
        selected_student_id_enroll_drop = st.selectbox("Select Student (Enroll/Drop)", options=[""] + student_ids, key="enroll_drop_student_select_admin")
        selected_course_filter_id_enroll_drop = st.selectbox("Filter Offerings by Course (Enroll/Drop)", options=course_ids_for_filter, key="course_filter_admin_enroll_drop")


        # Prepare available faculty assignments (offerings) for selection for enroll/drop
        available_offerings_df_enroll_drop = course_faculty_assignments_df.merge(courses_df, on='CourseID', how='left')
        available_offerings_df_enroll_drop = available_offerings_df_enroll_drop.merge(faculty_df, on='FacultyID', how='left')
        
        # Apply course filter if selected
        if selected_course_filter_id_enroll_drop:
            available_offerings_df_enroll_drop = available_offerings_df_enroll_drop[available_offerings_df_enroll_drop['CourseID'] == selected_course_filter_id_enroll_drop]

        # Filter out offerings where capacity is reached for that specific offering
        available_offerings_df_enroll_drop = available_offerings_df_enroll_drop.copy() # Use .copy() to avoid SettingWithCopyWarning
        available_offerings_df_enroll_drop['EnrolledStudents'] = pd.to_numeric(available_offerings_df_enroll_drop['EnrolledStudents'], errors='coerce').fillna(0).astype(int)
        available_offerings_df_enroll_drop['Capacity'] = pd.to_numeric(available_offerings_df_enroll_drop['Capacity'], errors='coerce').fillna(0).astype(int)

        available_offerings_df_enroll_drop = available_offerings_df_enroll_drop[
            available_offerings_df_enroll_drop.apply(
                lambda row: row['EnrolledStudents'] < row['Capacity'], axis=1
            )
        ]
        
        available_offering_display_options_enroll_drop = available_offerings_df_enroll_drop.apply(
            lambda row: f"{row['CourseName']} ({row['CourseID']}) - Faculty: {row['FacultyName']} ({row['FacultyID']}) - Offering ID: {row['ClassID']} (Enrolled: {row['EnrolledStudents']}/{row['Capacity']})",
            axis=1
        ).tolist()

        selected_offering_display_enroll_drop = st.selectbox(
            "Select Course Offering to Enroll Student In",
            options=[""] + available_offering_display_options_enroll_drop,
            key="enroll_offering_select_admin_enroll_drop"
        )

        # Initialize variables for enroll/drop
        selected_faculty_assignment_class_id_enroll_drop = None
        current_enrolled_in_offering_enroll_drop = 0
        capacity_of_offering_enroll_drop = 0
        is_student_enrolled_in_this_offering_enroll_drop = False
        student_enrollment_class_id_to_drop_enroll_drop = None


        if selected_student_id_enroll_drop and selected_offering_display_enroll_drop:
            # Extract FacultyAssignmentClassID from the display string
            selected_faculty_assignment_class_id_enroll_drop = selected_offering_display_enroll_drop.split('Offering ID: ')[1].split(' ')[0]

            # Get details of the selected faculty assignment (offering)
            offering_row_enroll_drop = get_row_by_id('course_faculty_assignments', 'ClassID', selected_faculty_assignment_class_id_enroll_drop)
            if not offering_row_enroll_drop:
                st.error("Selected faculty offering not found.")
                return
            
            # Explicitly cast to int here to prevent TypeError
            current_enrolled_in_offering_enroll_drop = int(offering_row_enroll_drop.get('EnrolledStudents', 0))
            capacity_of_offering_enroll_drop = int(offering_row_enroll_drop.get('Capacity', 0))

            # Check if student is already enrolled in this specific faculty offering
            is_student_enrolled_in_this_offering_enroll_drop = bool(((enrollments_df['StudentID'] == selected_student_id_enroll_drop) &
                                                      (enrollments_df['FacultyAssignmentClassID'] == selected_faculty_assignment_class_id_enroll_drop)).any())
            
            # Get student's enrollment ClassID for dropping, if exists
            if is_student_enrolled_in_this_offering_enroll_drop:
                student_enrollment_record_enroll_drop = enrollments_df[
                    (enrollments_df['StudentID'] == selected_student_id_enroll_drop) &
                    (enrollments_df['FacultyAssignmentClassID'] == selected_faculty_assignment_class_id_enroll_drop)
                ]
                if not student_enrollment_record_enroll_drop.empty:
                    student_enrollment_class_id_to_drop_enroll_drop = student_enrollment_record_enroll_drop.iloc[0]['ClassID']


            st.write(f"Selected Student: {selected_student_id_enroll_drop}")
            st.write(f"Selected Course Offering: {selected_offering_display_enroll_drop}")
            st.write(f"Offering ({selected_faculty_assignment_class_id_enroll_drop}) Enrolled: {current_enrolled_in_offering_enroll_drop}/{capacity_of_offering_enroll_drop}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Enroll Student", disabled=is_student_enrolled_in_this_offering_enroll_drop or current_enrolled_in_offering_enroll_drop >= capacity_of_offering_enroll_drop, key="admin_enroll_button"):
                    if not is_student_enrolled_in_this_offering_enroll_drop:
                        if current_enrolled_in_offering_enroll_drop < capacity_of_offering_enroll_drop:
                            conn = sqlite3.connect(DB_FILE)
                            cursor = conn.cursor()
                            try:
                                new_student_enrollment_class_id = generate_class_id(conn, cursor) # Generate new ClassID for student enrollment
                                cursor.execute(
                                    "INSERT INTO enrollments (ClassID, StudentID, FacultyAssignmentClassID) VALUES (?, ?, ?)",
                                    (new_student_enrollment_class_id, selected_student_id_enroll_drop, selected_faculty_assignment_class_id_enroll_drop)
                                )
                                # Update enrolled students count for this specific offering
                                cursor.execute(
                                    "UPDATE course_faculty_assignments SET EnrolledStudents = ? WHERE ClassID = ?",
                                    (current_enrolled_in_offering_enroll_drop + 1, selected_faculty_assignment_class_id_enroll_drop)
                                )
                                conn.commit()
                                st.success(f"Student {selected_student_id_enroll_drop} enrolled in offering {selected_faculty_assignment_class_id_enroll_drop} with Enrollment ClassID: {new_student_enrollment_class_id}.")
                                st.session_state.enrollment_data_updated = True
                                st.rerun()
                            except sqlite3.Error as e:
                                conn.rollback()
                                st.error(f"Failed to enroll student: {e}. Changes rolled back.")
                            finally:
                                conn.close()
                        else:
                            st.error("This specific offering capacity reached.")
                    else:
                        st.info("Student is already enrolled in this specific offering.")
            with col2:
                if st.button("Drop Student", disabled=not is_student_enrolled_in_this_offering_enroll_drop, key="admin_drop_button"):
                    if is_student_enrolled_in_this_offering_enroll_drop and student_enrollment_class_id_to_drop_enroll_drop:
                        conn = sqlite3.connect(DB_FILE)
                        cursor = conn.cursor()
                        try:
                            cursor.execute("DELETE FROM enrollments WHERE ClassID = ?", (student_enrollment_class_id_to_drop_enroll_drop,))
                            # Update enrolled students count for this specific offering
                            cursor.execute(
                                "UPDATE course_faculty_assignments SET EnrolledStudents = ? WHERE ClassID = ?",
                                (current_enrolled_in_offering_enroll_drop - 1, selected_faculty_assignment_class_id_enroll_drop)
                            )
                            conn.commit()
                            st.success(f"Student {selected_student_id_enroll_drop} dropped from offering {selected_faculty_assignment_class_id_enroll_drop}.")
                            st.session_state.enrollment_data_updated = True
                            st.rerun()
                        except sqlite3.Error as e:
                            conn.rollback()
                            st.error(f"Failed to drop student: {e}. Changes rolled back.")
                        finally:
                            conn.close()
                    else:
                        st.info("Student is not enrolled in this specific offering.")
        else:
            st.info("Select a student and a course offering to manage enrollment.")

        st.markdown("---")
        st.subheader("Current Student Enrollments Overview")
        if not enrollments_df.empty:
            # Merge with student, faculty assignment, course, and faculty names for better readability
            display_df = enrollments_df.merge(students_df, on='StudentID', how='left')
            display_df = display_df.merge(course_faculty_assignments_df, left_on='FacultyAssignmentClassID', right_on='ClassID', how='left')
            display_df = display_df.rename(columns={'ClassID_x': 'EnrollmentClassID', 'ClassID_y': 'FacultyAssignmentClassID_lookup'}) 
            display_df = display_df.merge(courses_df, on='CourseID', how='left')
            display_df = display_df.merge(faculty_df, on='FacultyID', how='left')

            st.dataframe(display_df[[
                'EnrollmentClassID', 'StudentID', 'StudentName', 
                'FacultyAssignmentClassID', 'CourseID', 'CourseName', 'FacultyID', 'FacultyName',
                'EnrolledStudents', 'Capacity' 
            ]].rename(columns={
                'EnrolledStudents': 'OfferingEnrolled',
                'Capacity': 'OfferingCapacity'
            }))
        else:
            st.info("No enrollments yet.")

    def swap_faculty_for_student(self):
        """Allows admin to swap faculty for an enrolled student's course."""
        st.subheader("Swap Faculty for Enrolled Student")
        students_df = load_table_to_df('students', ['StudentID', 'StudentName'])
        courses_df = load_table_to_df('courses', ['CourseID', 'CourseName', 'Credits']) # No capacity/enrolled here
        faculty_df = load_table_to_df('faculty', ['FacultyID', 'FacultyName'])
        
        # Load course_faculty_assignments with their capacity and enrolled students
        course_faculty_assignments_df = load_table_to_df(
            'course_faculty_assignments', 
            ['ClassID', 'CourseID', 'FacultyID', 'Capacity', 'EnrolledStudents']
        )
        enrollments_df = load_table_to_df('enrollments', ['ClassID', 'StudentID', 'FacultyAssignmentClassID'])

        if students_df.empty or courses_df.empty or course_faculty_assignments_df.empty:
            st.info("No students, courses, or faculty assignments available to swap faculty for.")
            return

        student_ids = students_df['StudentID'].tolist()
        selected_student_id_swap = st.selectbox("Select Student (Swap Faculty)", options=[""] + student_ids, key="swap_student_select_admin")

        current_student_enrollments_for_swap_df = pd.DataFrame()
        if selected_student_id_swap:
            conn = sqlite3.connect(DB_FILE)
            query_student_enrollments = """
                SELECT 
                    e.ClassID AS StudentEnrollmentClassID, 
                    e.FacultyAssignmentClassID,
                    cfa.CourseID,
                    c.CourseName,
                    f.FacultyName AS CurrentFacultyName,
                    cfa.Capacity,
                    cfa.EnrolledStudents
                FROM enrollments e
                JOIN course_faculty_assignments cfa ON e.FacultyAssignmentClassID = cfa.ClassID
                JOIN courses c ON cfa.CourseID = c.CourseID
                JOIN faculty f ON cfa.FacultyID = f.FacultyID
                WHERE e.StudentID = ?
                ORDER BY c.CourseID
            """
            current_student_enrollments_for_swap_df = pd.read_sql_query(query_student_enrollments, conn, params=(selected_student_id_swap,))
            conn.close()
        
        if current_student_enrollments_for_swap_df.empty:
            st.info("Selected student has no enrollments to swap faculty for.")
            selected_enrollment_for_swap_display = "" # Ensure this is empty if no enrollments
        else:
            current_student_enrollments_for_swap_df['Display'] = current_student_enrollments_for_swap_df.apply(
                lambda row: f"{row['CourseName']} ({row['CourseID']}) - Current Faculty: {row['CurrentFacultyName']} (Offering ID: {row['FacultyAssignmentClassID']}) - Your Enrollment ID: {row['StudentEnrollmentClassID']}",
                axis=1
            )
            selected_enrollment_for_swap_display = st.selectbox(
                "Select Student's Current Enrollment to Change Faculty For",
                options=[""] + current_student_enrollments_for_swap_df['Display'].tolist(),
                key="select_enrollment_to_swap_faculty"
            )

        new_faculty_offering_display = ""
        if selected_enrollment_for_swap_display:
            # Extract details of the selected enrollment
            selected_student_enrollment_class_id = selected_enrollment_for_swap_display.split('Your Enrollment ID: ')[1].strip()
            selected_enrollment_record = current_student_enrollments_for_swap_df[
                current_student_enrollments_for_swap_df['StudentEnrollmentClassID'] == selected_student_enrollment_class_id
            ].iloc[0]
            
            current_faculty_assignment_class_id = selected_enrollment_record['FacultyAssignmentClassID']
            course_id_of_selected_enrollment = selected_enrollment_record['CourseID']

            st.write(f"Selected Enrollment: {selected_enrollment_record['CourseName']} ({selected_enrollment_record['CourseID']}) with {selected_enrollment_record['CurrentFacultyName']}")

            # Find other offerings for the same CourseID
            other_offerings_for_course_df = course_faculty_assignments_df[
                (course_faculty_assignments_df['CourseID'] == course_id_of_selected_enrollment) &
                (course_faculty_assignments_df['ClassID'] != current_faculty_assignment_class_id) # Exclude current offering
            ].copy() # Use .copy() to avoid SettingWithCopyWarning
            
            if not other_offerings_for_course_df.empty:
                other_offerings_for_course_df = other_offerings_for_course_df.merge(faculty_df, on='FacultyID', how='left')
                other_offerings_for_course_df['Display'] = other_offerings_for_course_df.apply(
                    lambda row: f"Faculty: {row['FacultyName']} ({row['FacultyID']}) - Offering ID: {row['ClassID']} (Enrolled: {row['EnrolledStudents']}/{row['Capacity']})",
                    axis=1
                )
                new_faculty_offering_display = st.selectbox(
                    f"Select New Faculty Offering for {course_id_of_selected_enrollment}",
                    options=[""] + other_offerings_for_course_df['Display'].tolist(),
                    key="select_new_faculty_offering"
                )
            else:
                st.info(f"No other faculty offerings available for course {course_id_of_selected_enrollment}.")

            if new_faculty_offering_display:
                new_faculty_assignment_class_id = new_faculty_offering_display.split('Offering ID: ')[1].split(' ')[0]
                
                new_offering_details = get_row_by_id('course_faculty_assignments', 'ClassID', new_faculty_assignment_class_id)
                
                # Robust conversion for EnrolledStudents and Capacity
                enrolled_val_new = new_offering_details.get('EnrolledStudents', 0)
                if isinstance(enrolled_val_new, bytes):
                    try:
                        current_enrolled_in_new_offering = int(enrolled_val_new.decode('utf-8').strip() or 0)
                    except (UnicodeDecodeError, ValueError):
                        current_enrolled_in_new_offering = 0
                else:
                    current_enrolled_in_new_offering = int(enrolled_val_new)

                capacity_val_new = new_offering_details.get('Capacity', 0)
                if isinstance(capacity_val_new, bytes):
                    try:
                        capacity_of_new_offering = int(capacity_val_new.decode('utf-8').strip() or 0)
                    except (UnicodeDecodeError, ValueError):
                        capacity_of_new_offering = 0
                else:
                    capacity_of_new_offering = int(capacity_val_new)

                st.write(f"New Offering Details: {new_faculty_offering_display}")
                st.write(f"New Offering Capacity: {current_enrolled_in_new_offering}/{capacity_of_new_offering}")

                if st.button("Perform Faculty Swap", key="admin_faculty_swap_button"):
                    if current_enrolled_in_new_offering < capacity_of_new_offering:
                        conn = sqlite3.connect(DB_FILE)
                        cursor = conn.cursor()
                        try:
                            # 1. Update the student's enrollment to the new FacultyAssignmentClassID
                            cursor.execute(
                                "UPDATE enrollments SET FacultyAssignmentClassID = ? WHERE ClassID = ?",
                                (new_faculty_assignment_class_id, selected_student_enrollment_class_id)
                            )

                            # 2. Decrement enrolled students for the old offering
                            # Explicitly cast to int before arithmetic and database update
                            old_offering_enrolled = int(selected_enrollment_record['EnrolledStudents']) 
                            cursor.execute(
                                "UPDATE course_faculty_assignments SET EnrolledStudents = ? WHERE ClassID = ?",
                                (old_offering_enrolled - 1, current_faculty_assignment_class_id)
                            )

                            # 3. Increment enrolled students for the new offering
                            # Explicitly cast to int before arithmetic and database update
                            new_offering_enrolled = int(current_enrolled_in_new_offering)
                            cursor.execute(
                                "UPDATE course_faculty_assignments SET EnrolledStudents = ? WHERE ClassID = ?",
                                (new_offering_enrolled + 1, new_faculty_assignment_class_id)
                            )
                            
                            conn.commit()
                            st.success(f"Successfully swapped student {selected_student_id_swap}'s enrollment (ID: {selected_student_enrollment_class_id}) from offering {current_faculty_assignment_class_id} to {new_faculty_assignment_class_id}.")
                            st.session_state.enrollment_data_updated = True
                            st.rerun()
                        except sqlite3.Error as e:
                            conn.rollback()
                            st.error(f"Failed to swap faculty: {e}. Changes rolled back.")
                        finally:
                            conn.close()
                    else:
                        st.error("The selected new offering is full. Cannot swap.")
            else:
                st.info("Select a new faculty offering to perform the swap.")
        else:
            st.info("Select a student's enrollment to swap faculty for.")


    def view_all_faculty(self):
        """Displays all registered faculty members."""
        st.subheader("All Faculty Members")
        faculty_df = load_table_to_df('faculty', ['FacultyID', 'FacultyName'])
        if not faculty_df.empty:
            st.dataframe(faculty_df)
        else:
            st.info("No faculty members registered.")

    def view_all_students(self):
        """Displays all registered students."""
        st.subheader("All Students")
        students_df = load_table_to_df('students', ['StudentID', 'StudentName'])
        if not students_df.empty:
            st.dataframe(students_df)
        else:
            st.info("No students registered.")

    def view_all_courses(self):
        """Displays all course assignments (faculty offerings), with faculty assignment ClassID as the primary identifier."""
        st.subheader("All Course Assignments (Faculty Offerings)")
        
        # Join course_faculty_assignments with courses and faculty to get all details
        conn = sqlite3.connect(DB_FILE)
        query = """
            SELECT 
                cfa.ClassID AS FacultyAssignmentClassID,
                c.CourseID,
                c.CourseName,
                c.Credits,
                f.FacultyID,
                f.FacultyName,
                cfa.Capacity,         -- Capacity for this specific offering
                cfa.EnrolledStudents  -- Enrolled students for this specific offering
            FROM course_faculty_assignments cfa
            JOIN courses c ON cfa.CourseID = c.CourseID
            JOIN faculty f ON cfa.FacultyID = f.FacultyID
            ORDER BY cfa.ClassID
        """
        all_assignments_df = pd.read_sql_query(query, conn)
        conn.close()

        if not all_assignments_df.empty:
            st.dataframe(all_assignments_df[[
                'FacultyAssignmentClassID', 'CourseID', 'CourseName', 'Credits', 
                'FacultyID', 'FacultyName', 'Capacity', 'EnrolledStudents'
            ]].rename(columns={
                'Capacity': 'OfferingCapacity',
                'EnrolledStudents': 'OfferingEnrolled'
            }))
        else:
            st.info("No course assignments (faculty offerings) available.")

    def clear_all_enrollments(self):
        """Allows admin to clear all student enrollments and reset enrolled counts in offerings."""
        st.subheader("Clear All Enrollments")
        st.warning("🚨 DANGER ZONE: This action will permanently delete ALL student enrollment records and reset all 'EnrolledStudents' counts to 0. This cannot be undone.")

        if st.button("Confirm Clear All Enrollments", key="confirm_clear_all_enrollments_button"):
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            try:
                # 1. Delete all records from the enrollments table
                cursor.execute("DELETE FROM enrollments")
                
                # 2. Reset EnrolledStudents count to 0 for all course_faculty_assignments
                cursor.execute("UPDATE course_faculty_assignments SET EnrolledStudents = 0")
                
                conn.commit()
                st.success("All student enrollments cleared and all offering enrolled counts reset to 0 successfully.")
                st.session_state.enrollment_data_updated = True
                st.session_state.course_data_updated = True # Also update course data to reflect reset counts
                st.rerun()
            except sqlite3.Error as e:
                conn.rollback()
                st.error(f"Failed to clear all enrollments: {e}. Changes rolled back.")
            finally:
                conn.close()


class Faculty:
    """Represents a faculty member and their actions."""
    def __init__(self, faculty_id):
        self.faculty_id = faculty_id
        faculty_row = get_row_by_id('faculty', 'FacultyID', faculty_id)
        if faculty_row:
            self.faculty_name = faculty_row.get('FacultyName', "Unknown")
        else:
            self.faculty_name = "Unknown"
            st.error(f"Faculty ID {faculty_id} not found in records.")

    def check_assigned_courses(self):
        """Displays courses assigned to this faculty member, including the assignment ClassID, capacity, and enrolled students."""
        st.subheader(f"My Course Assignments ({self.faculty_name} - {self.faculty_id})")
        
        conn = sqlite3.connect(DB_FILE)
        query = """
            SELECT 
                cfa.ClassID AS MyAssignmentClassID, 
                c.CourseID, 
                c.CourseName, 
                c.Credits, 
                cfa.Capacity,         -- Capacity for this specific offering
                cfa.EnrolledStudents  -- Enrolled students for this specific offering
            FROM course_faculty_assignments cfa
            JOIN courses c ON cfa.CourseID = c.CourseID
            WHERE cfa.FacultyID = ?
            ORDER BY cfa.ClassID
        """
        my_courses_df = pd.read_sql_query(query, conn, params=(self.faculty_id,))
        conn.close()

        if not my_courses_df.empty:
            st.dataframe(my_courses_df[[
                'MyAssignmentClassID', 'CourseID', 'CourseName', 'Credits', 'Capacity', 'EnrolledStudents'
            ]].rename(columns={
                'Capacity': 'OfferingCapacity',
                'EnrolledStudents': 'OfferingEnrolled'
            }))
        else:
            st.info("No courses currently assigned to you.")

    def check_enrolled_students(self):
        """Displays students enrolled in courses assigned to this faculty member."""
        st.subheader(f"Students Enrolled in My Courses ({self.faculty_name})")
        
        conn = sqlite3.connect(DB_FILE)
        query = """
            SELECT 
                e.ClassID AS StudentEnrollmentClassID, 
                s.StudentID, 
                s.StudentName,
                cfa.ClassID AS FacultyAssignmentClassID, -- The specific assignment ID they enrolled under
                c.CourseID, 
                c.CourseName
            FROM enrollments e
            JOIN students s ON e.StudentID = s.StudentID
            JOIN course_faculty_assignments cfa ON e.FacultyAssignmentClassID = cfa.ClassID
            JOIN courses c ON cfa.CourseID = c.CourseID
            JOIN faculty f ON cfa.FacultyID = f.FacultyID
            WHERE cfa.FacultyID = ?
            ORDER BY c.CourseID, s.StudentID
        """
        enrolled_students_df = pd.read_sql_query(query, conn, params=(self.faculty_id,))
        conn.close()

        if not enrolled_students_df.empty:
            st.dataframe(enrolled_students_df[[
                'StudentEnrollmentClassID', 'StudentID', 'StudentName', 
                'FacultyAssignmentClassID', 'CourseID', 'CourseName'
            ]])
        else:
            st.info("No students enrolled in your courses yet.")

    def drop_and_assign_course(self):
        """Allows faculty to manage their assignment from a course or reassign it to another faculty."""
        st.subheader("Manage My Course Assignments")
        
        conn = sqlite3.connect(DB_FILE)
        query = """
            SELECT cfa.ClassID, c.CourseID, c.CourseName
            FROM courses c
            JOIN course_faculty_assignments cfa ON c.CourseID = cfa.CourseID
            WHERE cfa.FacultyID = ?
        """
        my_assigned_courses_df = pd.read_sql_query(query, conn, params=(self.faculty_id,))
        conn.close()

        faculty_df = load_table_to_df('faculty', ['FacultyID', 'FacultyName'])

        if my_assigned_courses_df.empty:
            st.info("You are not currently assigned to any courses to manage.")
            return

        # Create a display string for the selectbox including the assignment ClassID
        my_assigned_courses_df['Display'] = my_assigned_courses_df.apply(
            lambda row: f"{row['CourseID']} - {row['CourseName']} (Your Assignment ClassID: {row['ClassID']})",
            axis=1
        )

        selected_assignment_display = st.selectbox(
            "Select Your Course Assignment to Manage",
            options=[""] + my_assigned_courses_df['Display'].tolist(),
            key="faculty_manage_course_select"
        )

        if selected_assignment_display:
            # Extract CourseID and Assignment ClassID from the display string
            selected_course_id = selected_assignment_display.split(' - ')[0]
            selected_assignment_class_id = selected_assignment_display.split('ClassID: ')[1].strip(')')

            # Get the offering details to know its capacity and enrolled students
            offering_row = get_row_by_id('course_faculty_assignments', 'ClassID', selected_assignment_class_id)
            if not offering_row:
                st.error("Selected offering not found.")
                return
            
            # Robust conversion for EnrolledStudents and Capacity in Faculty class
            enrolled_val_faculty = offering_row.get('EnrolledStudents', 0)
            if isinstance(enrolled_val_faculty, bytes):
                try:
                    current_enrolled_in_offering_faculty = int(enrolled_val_faculty.decode('utf-8').strip() or 0)
                except (UnicodeDecodeError, ValueError):
                    current_enrolled_in_offering_faculty = 0
            else:
                current_enrolled_in_offering_faculty = int(enrolled_val_faculty)

            capacity_val_faculty = offering_row.get('Capacity', 0)
            if isinstance(capacity_val_faculty, bytes):
                try:
                    capacity_of_offering_faculty = int(capacity_val_faculty.decode('utf-8').strip() or 0)
                except (UnicodeDecodeError, ValueError):
                    capacity_of_offering_faculty = 0
            else:
                capacity_of_offering_faculty = int(capacity_val_faculty)

            st.write(f"Managing Course: {get_row_by_id('courses', 'CourseID', selected_course_id).get('CourseName')} ({selected_course_id})")
            st.write(f"Your Assignment ClassID: {selected_assignment_class_id}")
            st.write(f"Offering Enrolled: {current_enrolled_in_offering_faculty}/{capacity_of_offering_faculty}")


            col1, col2 = st.columns(2)

            with col1:
                # Option to drop the faculty's assignment from this course
                st.warning(f"This will remove your specific assignment (ClassID: {selected_assignment_class_id}) from {selected_course_id}.")
                st.warning("Note: This will also remove any student enrollments linked to this specific assignment.")
                if st.button(f"Remove My Assignment from {selected_course_id}"):
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    try:
                        # Deleting from course_faculty_assignments will cascade delete enrollments
                        cursor.execute("DELETE FROM course_faculty_assignments WHERE ClassID = ?", (selected_assignment_class_id,))
                        
                        conn.commit()
                        st.success(f"Your assignment (ClassID: {selected_assignment_class_id}) to course {selected_course_id} has been removed.")
                        st.session_state.course_data_updated = True
                        st.session_state.enrollment_data_updated = True # Enrollments might have changed
                        st.rerun() # Rerun to update the selectbox options
                    except sqlite3.Error as e:
                        conn.rollback()
                        st.error(f"Failed to remove assignment: {e}. Changes rolled back.")
                    finally:
                        conn.close()

            with col2:
                # Option to reassign this course to another faculty (from current faculty's perspective)
                # This means transferring *this* faculty's role to another by deleting current and adding new.
                available_faculty_ids = faculty_df['FacultyID'].tolist()
                # Remove current faculty from options for reassigning to someone else
                if self.faculty_id in available_faculty_ids:
                    available_faculty_ids.remove(self.faculty_id)

                if available_faculty_ids:
                    new_faculty_id_for_reassign = st.selectbox(
                        "Reassign this specific assignment to another Faculty",
                        options=[""] + available_faculty_ids,
                        key="reassign_faculty_select"
                    )
                    if st.button(f"Reassign {selected_course_id} to another"):
                        if new_faculty_id_for_reassign:
                            conn = sqlite3.connect(DB_FILE)
                            cursor = conn.cursor()
                            try:
                                # Check if the new faculty is already assigned to this course (any ClassID)
                                cursor.execute("SELECT 1 FROM course_faculty_assignments WHERE CourseID = ? AND FacultyID = ?", 
                                            (selected_course_id, new_faculty_id_for_reassign))
                                already_assigned = cursor.fetchone() is not None
                                
                                if already_assigned:
                                    st.warning(f"Faculty {new_faculty_id_for_reassign} is already assigned to {selected_course_id}. Your assignment will be removed.")
                                    # Just remove current faculty's assignment
                                    cursor.execute("DELETE FROM course_faculty_assignments WHERE ClassID = ?", (selected_assignment_class_id,))
                                    st.success(f"Your assignment (ClassID: {selected_assignment_class_id}) to {selected_course_id} has been removed.")
                                    st.session_state.course_data_updated = True
                                    st.rerun()
                                else:
                                    # Start a transaction to ensure atomicity for reassign
                                    # 1. Delete the current faculty's assignment (using its ClassID)
                                    # This will cascade delete student enrollments for this specific offering
                                    cursor.execute("DELETE FROM course_faculty_assignments WHERE ClassID = ?", (selected_assignment_class_id,))
                                    
                                    # 2. Create a new assignment for the new faculty (with a new ClassID)
                                    # The new assignment starts with the same capacity but 0 enrolled students
                                    new_class_id_for_reassign = generate_class_id(conn, cursor) # Pass connection/cursor
                                    cursor.execute(
                                        "INSERT INTO course_faculty_assignments (ClassID, CourseID, FacultyID, Capacity, EnrolledStudents) VALUES (?, ?, ?, ?, ?)",
                                        (new_class_id_for_reassign, selected_course_id, new_faculty_id_for_reassign, capacity_of_offering_faculty, 0) # Use the correctly converted capacity
                                    )
                                    conn.commit()
                                    st.success(f"Your assignment (ClassID: {selected_assignment_class_id}) for {selected_course_id} has been transferred to {new_faculty_id_for_reassign} (New ClassID: {new_class_id_for_reassign}).")
                                    st.session_state.course_data_updated = True
                                    st.rerun()
                            except sqlite3.Error as e:
                                conn.rollback()
                                st.error(f"Failed to reassign course: {e}. Changes rolled back.")
                            finally:
                                conn.close()
                        else:
                            st.warning("Please select a faculty to reassign to.")
                else:
                    st.info("No other faculty members to reassign to.")
        else:
            st.info("Select a course assignment to manage.")


class Student:
    """Represents a student and their actions."""
    def __init__(self, student_id):
        self.student_id = student_id
        student_row = get_row_by_id('students', 'StudentID', student_id)
        if student_row:
            self.student_name = student_row.get('StudentName', "Unknown")
        else:
            self.student_name = "Unknown"
            st.error(f"Student ID {student_id} not found in records.")

    def enroll_course(self):
        """Allows student to enroll in a course by selecting a faculty assignment (offering)."""
        st.subheader(f"Enroll in a Course ({self.student_name})")
        
        courses_df = load_table_to_df('courses', ['CourseID', 'CourseName', 'Credits'])
        faculty_df = load_table_to_df('faculty', ['FacultyID', 'FacultyName'])
        course_faculty_assignments_df = load_table_to_df('course_faculty_assignments', ['ClassID', 'CourseID', 'FacultyID', 'Capacity', 'EnrolledStudents'])
        enrollments_df = load_table_to_df('enrollments', ['ClassID', 'StudentID', 'FacultyAssignmentClassID'])

        # Get CourseIDs of all courses the student is currently enrolled in
        student_current_enrollment_course_ids = []
        if not enrollments_df.empty:
            student_enrollments_filtered = enrollments_df[enrollments_df['StudentID'] == self.student_id]
            if not student_enrollments_filtered.empty:
                # Merge with course_faculty_assignments to get CourseID for each enrollment
                enrolled_assignments = student_enrollments_filtered.merge(
                    course_faculty_assignments_df, 
                    left_on='FacultyAssignmentClassID', 
                    right_on='ClassID', 
                    how='left'
                )
                # Corrected: Access 'CourseID' directly, not 'CourseID_y'
                student_current_enrollment_course_ids = enrolled_assignments['CourseID'].tolist() 

        # Get available faculty assignments (offerings) that the student is NOT already enrolled in
        # and whose specific offering has capacity
        
        # Filter offerings by their individual capacity
        available_offerings_with_capacity_df = course_faculty_assignments_df.copy() # Use .copy() to avoid SettingWithCopyWarning
        available_offerings_with_capacity_df['EnrolledStudents'] = pd.to_numeric(available_offerings_with_capacity_df['EnrolledStudents'], errors='coerce').fillna(0).astype(int)
        available_offerings_with_capacity_df['Capacity'] = pd.to_numeric(available_offerings_with_capacity_df['Capacity'], errors='coerce').fillna(0).astype(int)

        available_offerings_with_capacity_df = available_offerings_with_capacity_df[
            available_offerings_with_capacity_df.apply(
                lambda row: row['EnrolledStudents'] < row['Capacity'], axis=1
            )
        ]

        # Then, filter out offerings the student is already enrolled in (by FacultyAssignmentClassID)
        student_enrolled_assignment_ids = enrollments_df[
            enrollments_df['StudentID'] == self.student_id
        ]['FacultyAssignmentClassID'].tolist()
        
        available_offerings_for_enrollment = available_offerings_with_capacity_df[
            ~available_offerings_with_capacity_df['ClassID'].isin(student_enrolled_assignment_ids)
        ]

        if available_offerings_for_enrollment.empty:
            st.info("No available course offerings to enroll in at the moment.")
            return

        # Prepare display options
        available_offerings_for_enrollment = available_offerings_for_enrollment.merge(courses_df, on='CourseID', how='left')
        available_offerings_for_enrollment = available_offerings_for_enrollment.merge(faculty_df, on='FacultyID', how='left')
        
        available_offerings_display_list = available_offerings_for_enrollment.apply(
            lambda row: f"{row['CourseName']} ({row['CourseID']}) - Faculty: {row['FacultyName']} ({row['FacultyID']}) - Offering ID: {row['ClassID']} (Enrolled: {row['EnrolledStudents']}/{row['Capacity']})",
            axis=1
        ).tolist()

        selected_offering_display = st.selectbox(
            "Select a course offering to enroll in (identified by Offering ID)",
            options=[""] + available_offerings_display_list,
            key="enroll_offering_select_student"
        )

        if selected_offering_display:
            # Extract the FacultyAssignmentClassID from the display string
            selected_faculty_assignment_class_id = selected_offering_display.split('Offering ID: ')[1].split(' ')[0]
            
            # Get the current enrollment status of this specific offering
            offering_row = get_row_by_id('course_faculty_assignments', 'ClassID', selected_faculty_assignment_class_id)
            if not offering_row:
                st.error("Selected faculty offering not found.")
                return
            
            current_enrolled_in_offering = offering_row.get('EnrolledStudents', 0)
            capacity_of_offering = offering_row.get('Capacity', 0)
            selected_course_id_for_enroll = offering_row.get('CourseID') # Get the CourseID of the selected offering

            # Check if student is already enrolled in this CourseID (for student-specific rule)
            if selected_course_id_for_enroll in student_current_enrollment_course_ids:
                st.error(f"You are already enrolled in a section of '{selected_course_id_for_enroll}'. You cannot enroll in the same course twice.")
                return # Prevent enrollment if already enrolled in this CourseID

            if st.button(f"Enroll in this offering (ID: {selected_faculty_assignment_class_id})"):
                if current_enrolled_in_offering < capacity_of_offering:
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    try:
                        new_student_enrollment_class_id = generate_class_id(conn, cursor) # Generate new ClassID for student enrollment
                        cursor.execute(
                            "INSERT INTO enrollments (ClassID, StudentID, FacultyAssignmentClassID) VALUES (?, ?, ?)",
                            (new_student_enrollment_class_id, self.student_id, selected_faculty_assignment_class_id)
                        )
                        # Update enrolled students count for this specific offering
                        cursor.execute(
                            "UPDATE course_faculty_assignments SET EnrolledStudents = ? WHERE ClassID = ?",
                            (current_enrolled_in_offering + 1, selected_faculty_assignment_class_id)
                        )
                        conn.commit()
                        st.success(f"Successfully enrolled in offering (ID: {selected_faculty_assignment_class_id}) with your Enrollment ClassID: {new_student_enrollment_class_id}.")
                        st.session_state.enrollment_data_updated = True
                        st.rerun() # Rerun to update available courses
                    except sqlite3.Error as e:
                        conn.rollback()
                        st.error(f"Failed to enroll: {e}. Changes rolled back.")
                    finally:
                        conn.close()
                else:
                    st.error("This specific offering is already full.")
        else:
            st.info("Select a course offering to enroll.")

    def view_my_courses(self):
        """Displays courses the student is currently enrolled in, showing both enrollment and faculty assignment ClassIDs."""
        st.subheader(f"My Enrolled Courses ({self.student_name})")
        
        conn = sqlite3.connect(DB_FILE)
        query = """
            SELECT 
                e.ClassID AS StudentEnrollmentClassID, 
                e.FacultyAssignmentClassID,
                c.CourseID, 
                c.CourseName, 
                c.Credits,
                f.FacultyID,
                f.FacultyName,
                cfa.Capacity,
                cfa.EnrolledStudents
            FROM enrollments e
            JOIN course_faculty_assignments cfa ON e.FacultyAssignmentClassID = cfa.ClassID
            JOIN courses c ON cfa.CourseID = c.CourseID
            JOIN faculty f ON cfa.FacultyID = f.FacultyID
            WHERE e.StudentID = ?
            ORDER BY c.CourseID, f.FacultyName
        """
        my_enrollments_df = pd.read_sql_query(query, conn, params=(self.student_id,))
        conn.close()

        if not my_enrollments_df.empty:
            st.dataframe(my_enrollments_df[[
                'StudentEnrollmentClassID', 'FacultyAssignmentClassID', 
                'CourseID', 'CourseName', 'Credits', 'FacultyID', 'FacultyName',
                'Capacity', 'EnrolledStudents'
            ]].rename(columns={
                'Capacity': 'OfferingCapacity',
                'EnrolledStudents': 'OfferingEnrolled'
            }))
        else:
            st.info("You are not currently enrolled in any courses.")

    def drop_course(self):
        """Allows student to drop an enrolled course."""
        st.subheader(f"Drop a Course ({self.student_name})")
        
        conn = sqlite3.connect(DB_FILE)
        query = """
            SELECT 
                e.ClassID AS StudentEnrollmentClassID, 
                e.FacultyAssignmentClassID,
                c.CourseID, 
                c.CourseName, 
                f.FacultyName,
                cfa.EnrolledStudents -- Get current enrolled count for the offering
            FROM enrollments e
            JOIN course_faculty_assignments cfa ON e.FacultyAssignmentClassID = cfa.ClassID
            JOIN courses c ON cfa.CourseID = c.CourseID
            JOIN faculty f ON cfa.FacultyID = f.FacultyID
            WHERE e.StudentID = ?
        """
        my_enrollments_df = pd.read_sql_query(query, conn, params=(self.student_id,))
        conn.close()

        if my_enrollments_df.empty:
            st.info("You are not enrolled in any courses to drop.")
            return

        drop_options = my_enrollments_df.apply(
            lambda row: f"{row['CourseName']} ({row['CourseID']}) - Faculty: {row['FacultyName']} - Your Enrollment ID: {row['StudentEnrollmentClassID']}",
            axis=1
        ).tolist()
        
        selected_drop_display = st.selectbox(
            "Select a course to drop",
            options=[""] + drop_options,
            key="drop_course_select"
        )

        if selected_drop_display:
            # Extract student's enrollment ClassID
            student_enrollment_class_id_to_drop = selected_drop_display.split('Your Enrollment ID: ')[1].strip()
            
            # Find the corresponding FacultyAssignmentClassID and current enrolled count for that offering
            enrollment_record = my_enrollments_df[my_enrollments_df['StudentEnrollmentClassID'] == student_enrollment_class_id_to_drop].iloc[0]
            faculty_assignment_class_id = enrollment_record['FacultyAssignmentClassID']
            current_enrolled_in_offering = enrollment_record['EnrolledStudents'] # This is the count for the offering

            if st.button(f"Confirm Drop (Your Enrollment ID: {student_enrollment_class_id_to_drop})"):
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                try:
                    cursor.execute("DELETE FROM enrollments WHERE ClassID = ?", (student_enrollment_class_id_to_drop,))
                    
                    # Decrement enrolled students count for this specific offering
                    cursor.execute(
                        "UPDATE course_faculty_assignments SET EnrolledStudents = ? WHERE ClassID = ?",
                        (current_enrolled_in_offering - 1, faculty_assignment_class_id)
                    )
                    conn.commit()
                    st.success(f"Successfully dropped your enrollment (ID: {student_enrollment_class_id_to_drop}).")
                    st.session_state.enrollment_data_updated = True
                    st.rerun()
                except sqlite3.Error as e:
                    conn.rollback()
                    st.error(f"Failed to drop course: {e}. Changes rolled back.")
                finally:
                    conn.close()
        else:
            st.info("Select a course to drop.")

    def swap_course(self):
        """Allows student to swap one enrolled course offering for another available course offering."""
        st.subheader(f"Swap Courses ({self.student_name})")
        
        courses_df = load_table_to_df('courses', ['CourseID', 'CourseName', 'Credits'])
        faculty_df = load_table_to_df('faculty', ['FacultyID', 'FacultyName'])
        course_faculty_assignments_df = load_table_to_df('course_faculty_assignments', ['ClassID', 'CourseID', 'FacultyID', 'Capacity', 'EnrolledStudents'])
        enrollments_df = load_table_to_df('enrollments', ['ClassID', 'StudentID', 'FacultyAssignmentClassID'])

        # Get student's current enrollments for the "drop" part
        conn = sqlite3.connect(DB_FILE)
        query_my_enrollments = """
            SELECT 
                e.ClassID AS StudentEnrollmentClassID, 
                e.FacultyAssignmentClassID,
                cfa.CourseID, 
                c.CourseName, 
                f.FacultyName,
                cfa.EnrolledStudents -- Get current enrolled count for the offering
            FROM enrollments e
            JOIN course_faculty_assignments cfa ON e.FacultyAssignmentClassID = cfa.ClassID
            JOIN courses c ON cfa.CourseID = c.CourseID
            JOIN faculty f ON cfa.FacultyID = f.FacultyID
            WHERE e.StudentID = ?
        """
        my_enrollments_df = pd.read_sql_query(query_my_enrollments, conn, params=(self.student_id,))
        conn.close()

        if my_enrollments_df.empty:
            st.info("You are not enrolled in any courses to swap.")
            return

        # Prepare drop options
        drop_options = my_enrollments_df.apply(
            lambda row: f"{row['CourseName']} ({row['CourseID']}) - Faculty: {row['FacultyName']} - Your Enrollment ID: {row['StudentEnrollmentClassID']}",
            axis=1
        ).tolist()

        selected_drop_display = st.selectbox(
            "Select course offering to drop",
            options=[""] + drop_options,
            key="swap_drop_course_select"
        )

        # Get available course offerings for the "enroll" part
        # Filter out offerings by their individual capacity
        available_offerings_with_capacity_df = course_faculty_assignments_df.copy() # Use .copy() to avoid SettingWithCopyWarning
        available_offerings_with_capacity_df['EnrolledStudents'] = pd.to_numeric(available_offerings_with_capacity_df['EnrolledStudents'], errors='coerce').fillna(0).astype(int)
        available_offerings_with_capacity_df['Capacity'] = pd.to_numeric(available_offerings_with_capacity_df['Capacity'], errors='coerce').fillna(0).astype(int)

        available_offerings_with_capacity_df = available_offerings_with_capacity_df[
            available_offerings_with_capacity_df.apply(
                lambda row: row['EnrolledStudents'] < row['Capacity'], axis=1
            )
        ]
        
        # Get CourseIDs of all courses the student is currently enrolled in (for the "enroll" part of swap)
        student_current_enrollment_course_ids = []
        if not enrollments_df.empty:
            student_enrollments_filtered = enrollments_df[enrollments_df['StudentID'] == self.student_id]
            if not student_enrollments_filtered.empty:
                enrolled_assignments = student_enrollments_filtered.merge(
                    course_faculty_assignments_df, 
                    left_on='FacultyAssignmentClassID', 
                    right_on='ClassID', 
                    how='left'
                )
                # Corrected: Access 'CourseID' directly, not 'CourseID_y'
                student_current_enrollment_course_ids = enrolled_assignments['CourseID'].tolist()

        available_offerings_for_enrollment = available_offerings_with_capacity_df[
            ~available_offerings_with_capacity_df['ClassID'].isin(my_enrollments_df['FacultyAssignmentClassID'].tolist()) # Exclude currently enrolled offerings
        ]

        if available_offerings_for_enrollment.empty:
            st.info("No available course offerings to swap into.")
            return

        available_offerings_for_enrollment = available_offerings_for_enrollment.merge(courses_df, on='CourseID', how='left')
        available_offerings_for_enrollment = available_offerings_for_enrollment.merge(faculty_df, on='FacultyID', how='left')
        
        available_enroll_options = available_offerings_for_enrollment.apply(
            lambda row: f"{row['CourseName']} ({row['CourseID']}) - Faculty: {row['FacultyName']} ({row['FacultyID']}) - Offering ID: {row['ClassID']} (Enrolled: {row['EnrolledStudents']}/{row['Capacity']})",
            axis=1
        ).tolist()

        selected_enroll_display = st.selectbox(
            "Select course offering to enroll in",
            options=[""] + available_enroll_options,
            key="swap_enroll_course_select"
        )

        if selected_drop_display and selected_enroll_display:
            # Extract IDs for drop
            student_enrollment_class_id_to_drop = selected_drop_display.split('Your Enrollment ID: ')[1].strip()
            drop_enrollment_record = my_enrollments_df[my_enrollments_df['StudentEnrollmentClassID'] == student_enrollment_class_id_to_drop].iloc[0]
            drop_faculty_assignment_class_id = drop_enrollment_record['FacultyAssignmentClassID']
            current_enrolled_in_dropped_offering = drop_enrollment_record['EnrolledStudents']
            dropped_course_id = drop_enrollment_record['CourseID'] # Get the CourseID of the dropped offering


            # Extract IDs for enroll
            selected_faculty_assignment_class_id_to_enroll = selected_enroll_display.split('Offering ID: ')[1].split(' ')[0]
            enroll_offering_row = get_row_by_id('course_faculty_assignments', 'ClassID', selected_faculty_assignment_class_id_to_enroll)
            
            # Robust conversion for EnrolledStudents and Capacity
            enrolled_val_new = enroll_offering_row.get('EnrolledStudents', 0)
            if isinstance(enrolled_val_new, bytes):
                try:
                    current_enrolled_in_new_offering = int(enrolled_val_new.decode('utf-8').strip() or 0)
                except (UnicodeDecodeError, ValueError):
                    current_enrolled_in_new_offering = 0
            else:
                current_enrolled_in_new_offering = int(enrolled_val_new)

            capacity_val_new = enroll_offering_row.get('Capacity', 0)
            if isinstance(capacity_val_new, bytes):
                try:
                    capacity_of_new_offering = int(capacity_val_new.decode('utf-8').strip() or 0)
                except (UnicodeDecodeError, ValueError):
                    capacity_of_new_offering = 0
            else:
                capacity_of_new_offering = int(capacity_val_new)


            new_enroll_course_id = enroll_offering_row.get('CourseID') # Get the CourseID of the new offering


            # Prevent swapping an offering for itself
            if drop_faculty_assignment_class_id == selected_faculty_assignment_class_id_to_enroll:
                st.error("Cannot swap an offering with itself.")
                return

            # Prevent swapping into a course ID the student is already enrolled in (excluding the one being dropped)
            # Temporarily remove the dropped course ID from the list for this check
            temp_enrolled_course_ids = [cid for cid in student_current_enrollment_course_ids if cid != dropped_course_id]
            if new_enroll_course_id in temp_enrolled_course_ids:
                st.error(f"You are already enrolled in a section of '{new_enroll_course_id}'. You cannot enroll in the same course twice.")
                return

            # Check capacity for the offering to enroll in
            if current_enrolled_in_new_offering >= capacity_of_new_offering:
                st.error(f"Offering {selected_faculty_assignment_class_id_to_enroll} is full. Cannot swap.")
                return

            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            try:
                # 1. Perform drop operation
                cursor.execute("DELETE FROM enrollments WHERE ClassID = ?", (student_enrollment_class_id_to_drop,))
                
                # Decrement enrolled students count for the dropped offering
                cursor.execute(
                    "UPDATE course_faculty_assignments SET EnrolledStudents = ? WHERE ClassID = ?",
                    (current_enrolled_in_dropped_offering - 1, drop_faculty_assignment_class_id)
                )
                
                # 2. Perform enroll operation
                new_student_enrollment_class_id = generate_class_id(conn, cursor)
                cursor.execute(
                    "INSERT INTO enrollments (ClassID, StudentID, FacultyAssignmentClassID) VALUES (?, ?, ?)",
                    (new_student_enrollment_class_id, self.student_id, selected_faculty_assignment_class_id_to_enroll)
                )
                # Increment enrolled students count for the new offering
                cursor.execute(
                    "UPDATE course_faculty_assignments SET EnrolledStudents = ? WHERE ClassID = ?",
                    (current_enrolled_in_new_offering + 1, selected_faculty_assignment_class_id_to_enroll)
                )
                
                conn.commit()
                st.success(f"Successfully swapped your enrollment (ID: {student_enrollment_class_id_to_drop}) for new enrollment (ID: {new_student_enrollment_class_id}).")
                st.session_state.enrollment_data_updated = True
                st.rerun()
            except sqlite3.Error as e:
                conn.rollback()
                st.error(f"Failed to swap courses: {e}. Changes rolled back.")
            finally:
                conn.close()
        else:
            st.info("Select both a course to drop and a course to enroll in.")


# --- Main Streamlit Application Logic ---

def main_app():
    """Main Streamlit application function."""
    st.set_page_config(layout="centered", page_title="Course Registration System")

    st.title("🎓 Course Registration System")

    # Initialize session state variables if they don't exist
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_role = None
        st.session_state.user_id = None
        st.session_state.faculty_data_updated = False
        st.session_state.student_data_updated = False
        st.session_state.course_data_updated = False
        st.session_state.enrollment_data_updated = False
    
    # Ensure default ADMIN user exists in SQLite
    admin_password_row = get_row_by_id('passwords', 'UserID', "ADMIN")
    if not admin_password_row:
        st.info("Adding default ADMIN user (ID: ADMIN, Pass: adminpass) to SQLite...")
        if execute_query("INSERT INTO passwords (UserID, Password, Role) VALUES (?, ?, ?)", ("ADMIN", "adminpass", "admin")):
            st.success("Default ADMIN user added.")
        else:
            st.error("Failed to add default ADMIN user.")
        st.rerun() # Rerun to update the state after adding admin

    # --- Logout Functionality ---
    if st.session_state.logged_in:
        st.sidebar.header(f"Logged in as: {st.session_state.user_role} ({st.session_state.user_id})")
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.user_role = None
            st.session_state.user_id = None
            st.success("Logged out successfully.")
            st.rerun() # Rerun to show login screen

    # --- Login/Role Selection ---
    if not st.session_state.logged_in:
        st.subheader("--- Select User Role ---")
        user_role_choice = st.radio(
            "Choose your role:",
            ('Student', 'Faculty', 'Admin'),
            key="user_role_radio"
        )

        # Automatically convert user_id_input to uppercase
        user_id_input = st.text_input(f"Enter your {user_role_choice} ID:").strip().upper()
        password_input = st.text_input("Enter Password:", type="password").strip()

        if st.button("Login"):
            if user_role_choice == 'Admin':
                if authenticate_admin_misc(user_id_input, password_input):
                    st.session_state.logged_in = True
                    st.session_state.user_role = 'Admin'
                    st.session_state.user_id = user_id_input
                    st.success("Admin login successful!")
                    st.rerun()
                else:
                    st.error("Admin login failed. Access denied.")
            elif user_role_choice == 'Faculty':
                if authenticate_faculty_student(user_id_input, password_input, 'faculty'):
                    st.session_state.logged_in = True
                    st.session_state.user_role = 'Faculty'
                    st.session_state.user_id = user_id_input
                    st.success("Faculty login successful!")
                    st.rerun()
                else:
                    st.error("Faculty login failed. Access denied.")
            elif user_role_choice == 'Student':
                if authenticate_faculty_student(user_id_input, password_input, 'student'):
                    st.session_state.logged_in = True
                    st.session_state.user_role = 'Student'
                    st.session_state.user_id = user_id_input
                    st.success("Student login successful!")
                    st.rerun()
                else:
                    st.error("Student login failed. Access denied.")
    else:
        # --- Display Menus based on Role ---
        if st.session_state.user_role == 'Admin':
            st.subheader(f"Admin Menu ({st.session_state.user_id})")
            admin_obj = Admin()
            admin_choice = st.sidebar.radio(
                "Admin Actions:",
                [
                    "Add New Faculty", "Add New Student", "Modify Faculty Details", "Modify Student Details",
                    "Create New Course Assignment", "Modify Existing Course Assignment", "Delete Course Assignment", 
                    "Manage Student Enrollments", "Swap Faculty for Student", 
                    "Clear All Enrollments", # New option
                    "Modify Global Class ID Sequence", 
                    "View All Faculty", "View All Students", "View All Course Assignments"
                ],
                key="admin_menu_radio"
            )

            if admin_choice == "Add New Faculty":
                admin_obj.add_new_faculty()
            elif admin_choice == "Add New Student":
                admin_obj.add_new_student()
            elif admin_choice == "Modify Faculty Details":
                admin_obj.modify_faculty()
            elif admin_choice == "Modify Student Details":
                admin_obj.modify_student()
            elif admin_choice == "Create New Course Assignment":
                admin_obj.create_course_assignment()
            elif admin_choice == "Modify Existing Course Assignment":
                admin_obj.modify_course_assignment()
            elif admin_choice == "Delete Course Assignment": 
                admin_obj.delete_course_assignment()
            elif admin_choice == "Manage Student Enrollments":
                admin_obj.manage_enrollments()
            elif admin_choice == "Swap Faculty for Student": 
                admin_obj.swap_faculty_for_student()
            elif admin_choice == "Clear All Enrollments": # Call the new method
                admin_obj.clear_all_enrollments()
            elif admin_choice == "Modify Global Class ID Sequence": 
                admin_obj.modify_class_id_sequence()
            elif admin_choice == "View All Faculty":
                admin_obj.view_all_faculty()
            elif admin_choice == "View All Students":
                admin_obj.view_all_students()
            elif admin_choice == "View All Course Assignments":
                admin_obj.view_all_courses()

        elif st.session_state.user_role == 'Faculty':
            st.subheader(f"Faculty Menu ({st.session_state.user_id})")
            faculty_obj = Faculty(st.session_state.user_id)
            faculty_choice = st.sidebar.radio(
                "Faculty Actions:",
                [
                    "Check Assigned Course Assignments",
                    "Check Enrolled Students in My Course Assignments",
                    "Manage My Course Assignments" # Renamed for clarity
                ],
                key="faculty_menu_radio"
            )

            if faculty_choice == "Check Assigned Course Assignments":
                faculty_obj.check_assigned_courses()
            elif faculty_choice == "Check Enrolled Students in My Course Assignments":
                faculty_obj.check_enrolled_students()
            elif faculty_choice == "Manage My Course Assignments":
                faculty_obj.drop_and_assign_course()

        elif st.session_state.user_role == 'Student':
            st.subheader(f"Student Menu ({st.session_state.user_id})")
            student_obj = Student(st.session_state.user_id)
            student_choice = st.sidebar.radio(
                "Student Actions:",
                [
                    "Enroll in a Course", "View My Enrolled Courses",
                    "Drop a Course", "Swap Courses"
                ],
                key="student_menu_radio"
            )

            if student_choice == "Enroll in a Course":
                student_obj.enroll_course()
            elif student_choice == "View My Enrolled Courses":
                student_obj.view_my_courses()
            elif student_choice == "Drop a Course":
                student_obj.drop_course()
            elif student_choice == "Swap Courses":
                student_obj.swap_course()

# --- Run the Streamlit App ---
if __name__ == "__main__":
    main_app()
