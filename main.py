import pandas as pd
import os
from typing import Optional, Dict, Any
from contextlib import contextmanager

# --- Configuration ---
class Config:
    DATA_FILE = 'data2.xlsx'
    SHEETS = {
        'COURSES': 'Courses',
        'FACULTY': 'Faculty', 
        'STUDENTS': 'Students',
        'ENROLLMENTS': 'Enrollments',
        'PASSWORDS': 'Passwords'
    }
    
    COLUMNS = {
        'COURSES': ['ClassID', 'CourseID', 'CourseName', 'FacultyID', 'Capacity'],
        'FACULTY': ['FacultyID', 'FacultyName', 'Password'],
        'STUDENTS': ['StudentID', 'StudentName', 'Password'],
        'ENROLLMENTS': ['StudentID', 'CourseID', 'ClassID'],
        'PASSWORDS': ['UserID', 'Password']
    }

# --- Data Access Layer ---
class DataManager:
    def __init__(self):
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Create Excel file with all sheets if it doesn't exist."""
        if not os.path.exists(Config.DATA_FILE):
            print(f"Creating {Config.DATA_FILE}...")
            with pd.ExcelWriter(Config.DATA_FILE, engine='xlsxwriter') as writer:
                for sheet_key, sheet_name in Config.SHEETS.items():
                    pd.DataFrame(columns=Config.COLUMNS[sheet_key]).to_excel(
                        writer, sheet_name=sheet_name, index=False
                    )
    
    def load_data(self, sheet_key: str) -> pd.DataFrame:
        """Load data from specified sheet."""
        sheet_name = Config.SHEETS[sheet_key]
        columns = Config.COLUMNS[sheet_key]
        
        try:
            xls = pd.ExcelFile(Config.DATA_FILE)
            if sheet_name not in xls.sheet_names:
                print(f"Creating empty sheet '{sheet_name}'...")
                df = pd.DataFrame(columns=columns)
                self.save_data(df, sheet_key)
                return df
            return pd.read_excel(Config.DATA_FILE, sheet_name=sheet_name)
        except Exception as e:
            print(f"Error loading data: {e}")
            return pd.DataFrame(columns=columns)
    
    def save_data(self, df: pd.DataFrame, sheet_key: str):
        """Save data to specified sheet."""
        sheet_name = Config.SHEETS[sheet_key]
        try:
            with pd.ExcelWriter(Config.DATA_FILE, engine='openpyxl', 
                              mode='a', if_sheet_exists='replace') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        except Exception as e:
            print(f"Error saving data: {e}")
    
    @contextmanager
    def batch_update(self):
        """Context manager for batch updates."""
        updates = {}
        
        class BatchUpdater:
            def __init__(self, data_manager):
                self.dm = data_manager
                self.updates = updates
            
            def update(self, sheet_key: str, df: pd.DataFrame):
                self.updates[sheet_key] = df
        
        yield BatchUpdater(self)
        
        # Save all updates
        for sheet_key, df in updates.items():
            self.save_data(df, sheet_key)

# --- Authentication Service ---
class AuthService:
    def __init__(self, data_manager: DataManager):
        self.dm = data_manager
    
    def authenticate_user(self, user_id: str, password: str, user_type: str) -> bool:
        """Unified authentication method."""
        if user_type == 'admin':
            return self._authenticate_misc(user_id, password)
        elif user_type in ['faculty', 'student']:
            return self._authenticate_faculty_student(user_id, password, user_type)
        return False
    
    def _authenticate_misc(self, user_id: str, password: str) -> bool:
        passwords_df = self.dm.load_data('PASSWORDS')
        user_entry = passwords_df[passwords_df['UserID'] == user_id]
        
        if user_entry.empty:
            print("User ID not found.")
            return False
        
        if user_entry['Password'].iloc[0] == password:
            return True
        
        print("Incorrect password.")
        return False
    
    def _authenticate_faculty_student(self, user_id: str, password: str, user_type: str) -> bool:
        sheet_key = 'FACULTY' if user_type == 'faculty' else 'STUDENTS'
        id_col = 'FacultyID' if user_type == 'faculty' else 'StudentID'
        
        user_df = self.dm.load_data(sheet_key)
        user_entry = user_df[user_df[id_col] == user_id]
        
        if user_entry.empty:
            print(f"{user_type.capitalize()} ID not found.")
            return False
        
        if user_entry['Password'].iloc[0] == password:
            return True
        
        print("Incorrect password.")
        return False

# --- Business Logic Services ---
class CourseService:
    def __init__(self, data_manager: DataManager):
        self.dm = data_manager
    
    def get_course_with_enrollment_info(self) -> pd.DataFrame:
        """Get courses with enrollment information."""
        courses_df = self.dm.load_data('COURSES')
        enrollments_df = self.dm.load_data('ENROLLMENTS')
        faculty_df = self.dm.load_data('FACULTY')
        
        if courses_df.empty:
            return pd.DataFrame()
        
        # Calculate enrollment counts
        enrollment_counts = enrollments_df.groupby('ClassID').size().reset_index(name='EnrolledCount')
        
        # Merge with courses
        display_df = pd.merge(courses_df, enrollment_counts, on='ClassID', how='left')
        display_df['EnrolledCount'] = display_df['EnrolledCount'].fillna(0).astype(int)
        
        # Calculate remaining seats
        display_df['Remaining Seats'] = display_df.apply(
            lambda row: row['Capacity'] - row['EnrolledCount'] if row['Capacity'] > 0 else 'Unlimited', 
            axis=1
        )
        
        # Add faculty names
        display_df = pd.merge(display_df, faculty_df[['FacultyID', 'FacultyName']], 
                             on='FacultyID', how='left')
        display_df['FacultyName'] = display_df['FacultyName'].fillna('N/A')
        
        return display_df
    
    def can_enroll(self, class_id: str) -> bool:
        """Check if enrollment is possible for a class."""
        courses_df = self.dm.load_data('COURSES')
        enrollments_df = self.dm.load_data('ENROLLMENTS')
        
        course = courses_df[courses_df['ClassID'] == class_id]
        if course.empty:
            return False
        
        capacity = course['Capacity'].iloc[0]
        if capacity == 0:  # Unlimited capacity
            return True
        
        current_count = enrollments_df[enrollments_df['ClassID'] == class_id].shape[0]
        return current_count < capacity
    
    def enroll_student(self, student_id: str, class_id: str) -> bool:
        """Enroll student in a class."""
        if not self.can_enroll(class_id):
            return False
        
        enrollments_df = self.dm.load_data('ENROLLMENTS')
        courses_df = self.dm.load_data('COURSES')
        
        # Check if already enrolled
        if not enrollments_df[(enrollments_df['StudentID'] == student_id) & 
                             (enrollments_df['ClassID'] == class_id)].empty:
            return False
        
        course = courses_df[courses_df['ClassID'] == class_id]
        if course.empty:
            return False
        
        # Add enrollment
        new_enrollment = pd.DataFrame([{
            'StudentID': student_id,
            'CourseID': course['CourseID'].iloc[0],
            'ClassID': class_id
        }])
        
        enrollments_df = pd.concat([enrollments_df, new_enrollment], ignore_index=True)
        self.dm.save_data(enrollments_df, 'ENROLLMENTS')
        return True
    
    def drop_student(self, student_id: str, class_id: str) -> bool:
        """Drop student from a class."""
        enrollments_df = self.dm.load_data('ENROLLMENTS')
        
        # Check if enrolled
        if enrollments_df[(enrollments_df['StudentID'] == student_id) & 
                         (enrollments_df['ClassID'] == class_id)].empty:
            return False
        
        # Remove enrollment
        enrollments_df = enrollments_df[~((enrollments_df['StudentID'] == student_id) & 
                                         (enrollments_df['ClassID'] == class_id))]
        self.dm.save_data(enrollments_df, 'ENROLLMENTS')
        return True

# --- User Classes ---
class BaseUser:
    def __init__(self, user_id: str, data_manager: DataManager, course_service: CourseService):
        self.user_id = user_id
        self.dm = data_manager
        self.course_service = course_service

class Admin(BaseUser):
    def __init__(self, data_manager: DataManager, course_service: CourseService):
        super().__init__('ADMIN', data_manager, course_service)
    
    def add_faculty(self):
        """Add new faculty member."""
        faculty_df = self.dm.load_data('FACULTY')
        
        faculty_id = input("Enter Faculty ID (e.g., F003): ").strip().upper()
        if faculty_id in faculty_df['FacultyID'].values:
            print("Faculty ID already exists.")
            return
        
        faculty_name = input("Enter Faculty Name: ").strip()
        password = input("Enter Password: ").strip()
        
        new_faculty = pd.DataFrame([{
            'FacultyID': faculty_id,
            'FacultyName': faculty_name,
            'Password': password
        }])
        
        faculty_df = pd.concat([faculty_df, new_faculty], ignore_index=True)
        self.dm.save_data(faculty_df, 'FACULTY')
        print(f"Faculty '{faculty_name}' ({faculty_id}) added successfully.")
    
    def add_student(self):
        """Add new student."""
        students_df = self.dm.load_data('STUDENTS')
        
        student_id = input("Enter Student ID (e.g., S003): ").strip().upper()
        if student_id in students_df['StudentID'].values:
            print("Student ID already exists.")
            return
        
        student_name = input("Enter Student Name: ").strip()
        password = input("Enter Password: ").strip()
        
        new_student = pd.DataFrame([{
            'StudentID': student_id,
            'StudentName': student_name,
            'Password': password
        }])
        
        students_df = pd.concat([students_df, new_student], ignore_index=True)
        self.dm.save_data(students_df, 'STUDENTS')
        print(f"Student '{student_name}' ({student_id}) added successfully.")
    
    def create_course(self):
        """Create new course assignment."""
        courses_df = self.dm.load_data('COURSES')
        faculty_df = self.dm.load_data('FACULTY')
        
        class_id = input("Enter Class ID (e.g., 2024251000456): ").strip().upper()
        if class_id in courses_df['ClassID'].values:
            print("Class ID already exists.")
            return
        
        course_id = input("Enter Course ID (e.g., CS101): ").strip().upper()
        course_name = input("Enter Course Name: ").strip()
        faculty_id = input("Enter Faculty ID (e.g., F001): ").strip().upper()
        
        if faculty_id not in faculty_df['FacultyID'].values:
            print(f"Warning: Faculty ID '{faculty_id}' does not exist.")
        
        try:
            capacity = int(input("Enter capacity (0 for unlimited): ") or "0")
        except ValueError:
            capacity = 0
        
        new_course = pd.DataFrame([{
            'ClassID': class_id,
            'CourseID': course_id,
            'CourseName': course_name,
            'FacultyID': faculty_id,
            'Capacity': capacity
        }])
        
        courses_df = pd.concat([courses_df, new_course], ignore_index=True)
        self.dm.save_data(courses_df, 'COURSES')
        print(f"Course '{course_name}' created successfully.")
    
    def view_all_courses(self):
        """View all courses with enrollment info."""
        display_df = self.course_service.get_course_with_enrollment_info()
        
        if not display_df.empty:
            print("\n--- All Course Assignments ---")
            print(display_df[['ClassID', 'CourseID', 'CourseName', 'FacultyName', 
                             'Capacity', 'Remaining Seats']].to_string(index=False))
        else:
            print("No course assignments available.")
    
    def view_all_faculty(self):
        """View all faculty members."""
        faculty_df = self.dm.load_data('FACULTY')
        if not faculty_df.empty:
            print("\n--- All Faculty ---")
            print(faculty_df[['FacultyID', 'FacultyName']].to_string(index=False))
        else:
            print("No faculty added yet.")
    
    def view_all_students(self):
        """View all students."""
        students_df = self.dm.load_data('STUDENTS')
        if not students_df.empty:
            print("\n--- All Students ---")
            print(students_df[['StudentID', 'StudentName']].to_string(index=False))
        else:
            print("No students added yet.")

class Faculty(BaseUser):
    def __init__(self, faculty_id: str, data_manager: DataManager, course_service: CourseService):
        super().__init__(faculty_id, data_manager, course_service)
        faculty_df = self.dm.load_data('FACULTY')
        faculty_row = faculty_df[faculty_df['FacultyID'] == faculty_id]
        self.name = faculty_row['FacultyName'].iloc[0] if not faculty_row.empty else "Unknown"
    
    def view_assigned_courses(self):
        """View courses assigned to this faculty."""
        display_df = self.course_service.get_course_with_enrollment_info()
        assigned_courses = display_df[display_df['FacultyID'] == self.user_id]
        
        if not assigned_courses.empty:
            print(f"\n--- Courses Assigned to {self.name} ({self.user_id}) ---")
            print(assigned_courses[['ClassID', 'CourseID', 'CourseName', 
                                   'Capacity', 'Remaining Seats']].to_string(index=False))
        else:
            print(f"No courses assigned to {self.name}.")
    
    def view_enrolled_students(self):
        """View students enrolled in faculty's courses."""
        courses_df = self.dm.load_data('COURSES')
        enrollments_df = self.dm.load_data('ENROLLMENTS')
        students_df = self.dm.load_data('STUDENTS')
        
        assigned_courses = courses_df[courses_df['FacultyID'] == self.user_id]
        
        if assigned_courses.empty:
            print(f"No courses assigned to {self.name}.")
            return
        
        print(f"\n--- Enrolled Students for {self.name} ({self.user_id}) ---")
        
        for _, course in assigned_courses.iterrows():
            class_id = course['ClassID']
            course_name = course['CourseName']
            
            enrolled_students = enrollments_df[enrollments_df['ClassID'] == class_id]
            student_details = pd.merge(enrolled_students, students_df, on='StudentID', how='left')
            
            print(f"\nCourse: {course_name} (ClassID: {class_id})")
            if not student_details.empty:
                for _, student in student_details.iterrows():
                    print(f"  - {student['StudentID']} ({student['StudentName']})")
            else:
                print("  No students enrolled.")

class Student(BaseUser):
    def __init__(self, student_id: str, data_manager: DataManager, course_service: CourseService):
        super().__init__(student_id, data_manager, course_service)
        students_df = self.dm.load_data('STUDENTS')
        student_row = students_df[students_df['StudentID'] == student_id]
        self.name = student_row['StudentName'].iloc[0] if not student_row.empty else "Unknown"
    
    def enroll_in_course(self):
        """Enroll in a course."""
        courses_df = self.dm.load_data('COURSES')
        
        if courses_df.empty:
            print("No courses available.")
            return
        
        # Show available courses
        unique_courses = courses_df['CourseID'].unique()
        print("\n--- Available Courses ---")
        for course_id in unique_courses:
            course_name = courses_df[courses_df['CourseID'] == course_id]['CourseName'].iloc[0]
            print(f"- {course_id} ({course_name})")
        
        course_id = input("Enter Course ID: ").strip().upper()
        available_classes = courses_df[courses_df['CourseID'] == course_id]
        
        if available_classes.empty:
            print("Invalid Course ID.")
            return
        
        # Show available classes for the course
        display_df = self.course_service.get_course_with_enrollment_info()
        eligible_classes = display_df[
            (display_df['CourseID'] == course_id) & 
            ((display_df['Capacity'] == 0) | (display_df['Remaining Seats'] > 0))
        ]
        
        if eligible_classes.empty:
            print("No available classes for this course.")
            return
        
        print(f"\n--- Available Classes for {course_id} ---")
        print(eligible_classes[['ClassID', 'FacultyName', 'Capacity', 
                               'Remaining Seats']].to_string(index=False))
        
        class_id = input("Enter Class ID: ").strip().upper()
        
        if self.course_service.enroll_student(self.user_id, class_id):
            print(f"Successfully enrolled in {course_id} (ClassID: {class_id}).")
        else:
            print("Enrollment failed. Class may be full or you're already enrolled.")
    
    def drop_course(self):
        """Drop an enrolled course."""
        enrollments_df = self.dm.load_data('ENROLLMENTS')
        courses_df = self.dm.load_data('COURSES')
        
        my_enrollments = enrollments_df[enrollments_df['StudentID'] == self.user_id]
        
        if my_enrollments.empty:
            print("You are not enrolled in any courses.")
            return
        
        # Show enrolled courses
        enrolled_details = pd.merge(my_enrollments, courses_df, on='ClassID', how='left')
        print(f"\n--- Your Enrolled Courses ---")
        print(enrolled_details[['ClassID', 'CourseID', 'CourseName']].to_string(index=False))
        
        class_id = input("Enter Class ID to drop: ").strip().upper()
        
        if self.course_service.drop_student(self.user_id, class_id):
            print(f"Successfully dropped from ClassID: {class_id}.")
        else:
            print("Drop failed. You may not be enrolled in this class.")
    
    def view_my_courses(self):
        """View enrolled courses."""
        enrollments_df = self.dm.load_data('ENROLLMENTS')
        
        my_enrollments = enrollments_df[enrollments_df['StudentID'] == self.user_id]
        
        if my_enrollments.empty:
            print(f"No courses enrolled by {self.name}.")
            return
        
        # Get detailed course information
        courses_df = self.dm.load_data('COURSES')
        faculty_df = self.dm.load_data('FACULTY')
        
        enrolled_details = pd.merge(my_enrollments, courses_df, on='ClassID', how='left')
        enrolled_details = pd.merge(enrolled_details, faculty_df[['FacultyID', 'FacultyName']], 
                                   on='FacultyID', how='left')
        enrolled_details['FacultyName'] = enrolled_details['FacultyName'].fillna('N/A')
        
        print(f"\n--- Courses Enrolled by {self.name} ({self.user_id}) ---")
        print(enrolled_details[['ClassID', 'CourseID', 'CourseName', 
                               'FacultyName']].to_string(index=False))

# --- Main Application ---
class CourseRegistrationSystem:
    def __init__(self):
        self.dm = DataManager()
        self.auth_service = AuthService(self.dm)
        self.course_service = CourseService(self.dm)
        self._initialize_admin()
    
    def _initialize_admin(self):
        """Initialize default admin user."""
        passwords_df = self.dm.load_data('PASSWORDS')
        if "ADMIN" not in passwords_df['UserID'].values:
            print("Adding default ADMIN user...")
            new_admin = pd.DataFrame([{'UserID': 'ADMIN', 'Password': 'adminpass'}])
            passwords_df = pd.concat([passwords_df, new_admin], ignore_index=True)
            self.dm.save_data(passwords_df, 'PASSWORDS')
    
    def run(self):
        """Main application loop."""
        print("--- Welcome to the Course Registration System ---")
        
        while True:
            print("\n--- Select User Role ---")
            print("1. Student")
            print("2. Faculty") 
            print("3. Admin")
            print("4. Exit")
            
            choice = input("Enter your choice: ").strip()
            
            if choice == '1':
                self._handle_student_login()
            elif choice == '2':
                self._handle_faculty_login()
            elif choice == '3':
                self._handle_admin_login()
            elif choice == '4':
                print("Goodbye!")
                break
            else:
                print("Invalid choice.")
    
    def _handle_student_login(self):
        """Handle student login and menu."""
        student_id = input("Enter Student ID: ").strip().upper()
        password = input("Enter Password: ").strip()
        
        if not self.auth_service.authenticate_user(student_id, password, 'student'):
            print("Login failed.")
            return
        
        student = Student(student_id, self.dm, self.course_service)
        
        while True:
            print(f"\n--- Student Menu ({student.name} - {student.user_id}) ---")
            print("1. Enroll in Course")
            print("2. View My Courses")
            print("3. Drop Course")
            print("4. Logout")
            
            choice = input("Enter choice: ").strip()
            
            if choice == '1':
                student.enroll_in_course()
            elif choice == '2':
                student.view_my_courses()
            elif choice == '3':
                student.drop_course()
            elif choice == '4':
                break
            else:
                print("Invalid choice.")
    
    def _handle_faculty_login(self):
        """Handle faculty login and menu."""
        faculty_id = input("Enter Faculty ID: ").strip().upper()
        password = input("Enter Password: ").strip()
        
        if not self.auth_service.authenticate_user(faculty_id, password, 'faculty'):
            print("Login failed.")
            return
        
        faculty = Faculty(faculty_id, self.dm, self.course_service)
        
        while True:
            print(f"\n--- Faculty Menu ({faculty.name} - {faculty.user_id}) ---")
            print("1. View Assigned Courses")
            print("2. View Enrolled Students")
            print("3. Logout")
            
            choice = input("Enter choice: ").strip()
            
            if choice == '1':
                faculty.view_assigned_courses()
            elif choice == '2':
                faculty.view_enrolled_students()
            elif choice == '3':
                break
            else:
                print("Invalid choice.")
    
    def _handle_admin_login(self):
        """Handle admin login and menu."""
        password = input("Enter Admin Password: ").strip()
        
        if not self.auth_service.authenticate_user("ADMIN", password, 'admin'):
            print("Login failed.")
            return
        
        admin = Admin(self.dm, self.course_service)
        
        while True:
            print("\n--- Admin Menu ---")
            print("1. Add Faculty")
            print("2. Add Student")
            print("3. Create Course")
            print("4. View All Courses")
            print("5. View All Faculty")
            print("6. View All Students")
            print("7. Logout")
            
            choice = input("Enter choice: ").strip()
            
            if choice == '1':
                admin.add_faculty()
            elif choice == '2':
                admin.add_student()
            elif choice == '3':
                admin.create_course()
            elif choice == '4':
                admin.view_all_courses()
            elif choice == '5':
                admin.view_all_faculty()
            elif choice == '6':
                admin.view_all_students()
            elif choice == '7':
                break
            else:
                print("Invalid choice.")

if __name__ == "__main__":
    system = CourseRegistrationSystem()
    system.run()