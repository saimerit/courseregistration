import pandas as pd
import os

# --- Excel File Path ---
DATA_FILE = 'data2.xlsx'

# --- Sheet Names ---
COURSES_SHEET = 'Courses'
FACULTY_SHEET = 'Faculty'
STUDENTS_SHEET = 'Students'
ENROLLMENTS_SHEET = 'Enrollments'
PASSWORDS_SHEET = 'Passwords'

# --- Helper Functions for Data Loading/Saving ---

def load_data(sheet_name, columns):
    """
    Loads data from a specific sheet in the Excel file.
    Creates the Excel file and/or sheet with empty columns if they don't exist.
    """
    if not os.path.exists(DATA_FILE):
        print(f"Creating empty {DATA_FILE}...")
        # Create an empty Excel file with all necessary sheets
        with pd.ExcelWriter(DATA_FILE, engine='xlsxwriter') as writer:
            pd.DataFrame(columns=['ClassID', 'CourseID', 'CourseName', 'FacultyID', 'Capacity']).to_excel(writer, sheet_name=COURSES_SHEET, index=False)
            pd.DataFrame(columns=['FacultyID', 'FacultyName', 'Password']).to_excel(writer, sheet_name=FACULTY_SHEET, index=False)
            pd.DataFrame(columns=['StudentID', 'StudentName', 'Password']).to_excel(writer, sheet_name=STUDENTS_SHEET, index=False)
            pd.DataFrame(columns=['StudentID', 'CourseID', 'ClassID']).to_excel(writer, sheet_name=ENROLLMENTS_SHEET, index=False)
            pd.DataFrame(columns=['UserID', 'Password']).to_excel(writer, sheet_name=PASSWORDS_SHEET, index=False)
        return pd.read_excel(DATA_FILE, sheet_name=sheet_name)

    xls = pd.ExcelFile(DATA_FILE)
    if sheet_name not in xls.sheet_names:
        print(f"Creating empty sheet '{sheet_name}' in {DATA_FILE}...")
        df = pd.DataFrame(columns=columns)
        save_data(df, sheet_name) # Save empty DataFrame to create the sheet
        return df
    
    return pd.read_excel(DATA_FILE, sheet_name=sheet_name)

def save_data(df, sheet_name):
    """Saves data to a specific sheet in the Excel file, preserving other sheets."""
    with pd.ExcelWriter(DATA_FILE, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)

def authenticate_admin_misc(user_id, password):
    """Authenticates Admin or other miscellaneous users against the Passwords sheet."""
    passwords_df = load_data(PASSWORDS_SHEET, ['UserID', 'Password'])
    
    user_entry = passwords_df[passwords_df['UserID'] == user_id]
    if user_entry.empty:
        print("User ID not found in miscellaneous users.")
        return False
    
    if user_entry['Password'].iloc[0] == password:
        return True
    else:
        print("Incorrect password.")
        return False

def authenticate_faculty_student(user_id, password, user_type):
    """Authenticates a Faculty or Student user against their respective sheets."""
    if user_type == 'faculty':
        user_df = load_data(FACULTY_SHEET, ['FacultyID', 'FacultyName', 'Password'])
        id_col = 'FacultyID'
    elif user_type == 'student':
        user_df = load_data(STUDENTS_SHEET, ['StudentID', 'StudentName', 'Password'])
        id_col = 'StudentID'
    else:
        return False
    
    user_entry = user_df[user_df[id_col] == user_id]
    if user_entry.empty:
        print(f"{user_type.capitalize()} ID not found.")
        return False
    
    if user_entry['Password'].iloc[0] == password:
        return True
    else:
        print("Incorrect password.")
        return False

# --- Admin Class ---
class Admin:
    def __init__(self):
        pass

    def add_new_faculty(self):
        """Admin adds a new faculty member with password."""
        faculty_df = load_data(FACULTY_SHEET, ['FacultyID', 'FacultyName', 'Password'])
        
        faculty_id = input("Enter new Faculty ID (e.g., F003): ").strip().upper()
        if faculty_id in faculty_df['FacultyID'].values:
            print("Faculty ID already exists. Please use a unique ID.")
            return

        faculty_name = input("Enter Faculty Name: ").strip()
        password = input("Enter Password for Faculty: ").strip()

        new_faculty = pd.DataFrame([{
            'FacultyID': faculty_id,
            'FacultyName': faculty_name,
            'Password': password
        }])
        faculty_df = pd.concat([faculty_df, new_faculty], ignore_index=True)
        save_data(faculty_df, FACULTY_SHEET)
        print(f"Faculty '{faculty_name}' ({faculty_id}) added successfully.")

    def add_new_student(self):
        """Admin adds a new student with password."""
        students_df = load_data(STUDENTS_SHEET, ['StudentID', 'StudentName', 'Password'])
        
        student_id = input("Enter new Student ID (e.g., S003): ").strip().upper()
        if student_id in students_df['StudentID'].values:
            print("Student ID already exists. Please use a unique ID.")
            return

        student_name = input("Enter Student Name: ").strip()
        password = input("Enter Password for Student: ").strip()

        new_student = pd.DataFrame([{
            'StudentID': student_id,
            'StudentName': student_name,
            'Password': password
        }])
        students_df = pd.concat([students_df, new_student], ignore_index=True)
        save_data(students_df, STUDENTS_SHEET)
        print(f"Student '{student_name}' ({student_id}) added successfully.")

    def create_course_assignment(self):
        """Admin creates a new course assignment (CourseID + FacultyID) with capacity and manually provided ClassID."""
        courses_df = load_data(COURSES_SHEET, ['ClassID', 'CourseID', 'CourseName', 'FacultyID', 'Capacity'])
        faculty_df = load_data(FACULTY_SHEET, ['FacultyID', 'FacultyName', 'Password'])

        class_id = input("Enter the new Class ID (e.g., 2024251000456): ").strip().upper()
        if class_id in courses_df['ClassID'].values:
            print("Class ID already exists. Please enter a unique Class ID.")
            return

        course_id = input("Enter Course ID (e.g., CS101): ").strip().upper()
        course_name = input("Enter Course Name: ").strip()
        faculty_id = input("Enter Faculty ID to assign this course (e.g., F001): ").strip().upper()
        
        if faculty_id not in faculty_df['FacultyID'].values:
            print(f"Warning: Faculty ID '{faculty_id}' does not exist. Course assignment created anyway, but assign to an existing faculty for proper functionality.")
        
        capacity = input("Enter capacity for this course assignment (e.g., 50, leave blank for no limit): ")
        try:
            capacity = int(capacity) if capacity else 0
        except ValueError:
            print("Invalid capacity. Setting to default 0 (no limit).")
            capacity = 0

        new_assignment = pd.DataFrame([{
            'ClassID': class_id,
            'CourseID': course_id,
            'CourseName': course_name,
            'FacultyID': faculty_id,
            'Capacity': capacity
        }])
        courses_df = pd.concat([courses_df, new_assignment], ignore_index=True)
        save_data(courses_df, COURSES_SHEET)
        print(f"Course assignment '{course_name}' ({course_id}) with Faculty {faculty_id} (ClassID: {class_id}) created successfully.")

    def modify_course_assignment(self):
        """Admin modifies an existing course assignment."""
        courses_df = load_data(COURSES_SHEET, ['ClassID', 'CourseID', 'CourseName', 'FacultyID', 'Capacity'])
        faculty_df = load_data(FACULTY_SHEET, ['FacultyID', 'FacultyName', 'Password'])
        
        if courses_df.empty:
            print("No course assignments to modify.")
            return

        print("\n--- Current Course Assignments ---")
        enrollments_df = load_data(ENROLLMENTS_SHEET, ['StudentID', 'CourseID', 'ClassID'])
        display_df = courses_df.copy()
        
        enrollment_counts = enrollments_df.groupby('ClassID').size().reset_index(name='EnrolledCount')
        display_df = pd.merge(display_df, enrollment_counts, on='ClassID', how='left')
        display_df['EnrolledCount'] = display_df['EnrolledCount'].fillna(0).astype(int)

        display_df['Remaining Seats'] = display_df.apply(lambda row: row['Capacity'] - row['EnrolledCount'] if row['Capacity'] > 0 else 'Unlimited', axis=1)
        
        display_df = pd.merge(display_df, faculty_df[['FacultyID', 'FacultyName']], on='FacultyID', how='left')
        display_df['FacultyName'] = display_df['FacultyName'].fillna('N/A')

        print(display_df[['ClassID', 'CourseID', 'CourseName', 'FacultyName', 'Capacity', 'Remaining Seats']].to_string(index=False))

        class_id_to_modify = input("Enter Class ID to modify: ").strip().upper()

        target_row = courses_df[courses_df['ClassID'] == class_id_to_modify]

        if target_row.empty:
            print("Class ID not found.")
            return

        idx = target_row.index[0]

        current_faculty_id = courses_df.loc[idx, 'FacultyID']
        current_faculty_name = faculty_df[faculty_df['FacultyID'] == current_faculty_id]['FacultyName'].iloc[0] if current_faculty_id in faculty_df['FacultyID'].values else "N/A"

        print(f"Modifying Assignment: {class_id_to_modify} - {courses_df.loc[idx, 'CourseName']} (Faculty: {current_faculty_name})")
        
        new_name = input(f"Enter new Course Name (current: {courses_df.loc[idx, 'CourseName']}), press Enter to keep current: ").strip()
        if new_name:
            courses_df.loc[idx, 'CourseName'] = new_name

        print("\n--- Available Faculty ---")
        if not faculty_df.empty:
            print(faculty_df[['FacultyID', 'FacultyName']].to_string(index=False))
        else:
            print("No faculty registered in the system.")

        new_faculty_id = input(f"Enter new Faculty ID to assign (current: {current_faculty_id} - {current_faculty_name}), press Enter to keep current: ").strip().upper()
        if new_faculty_id:
            if new_faculty_id in faculty_df['FacultyID'].values:
                courses_df.loc[idx, 'FacultyID'] = new_faculty_id
                print(f"Faculty for {class_id_to_modify} changed to {new_faculty_id}.")
            else:
                print(f"Error: Faculty ID '{new_faculty_id}' not found. Keeping current faculty.")

        new_capacity = input(f"Enter new Capacity (current: {courses_df.loc[idx, 'Capacity']}), press Enter to keep current: ").strip()
        if new_capacity:
            try:
                capacity_val = int(new_capacity)
                current_enrollment_count = enrollments_df[enrollments_df['ClassID'] == class_id_to_modify].shape[0]
                if capacity_val > 0 and current_enrollment_count > capacity_val:
                    print(f"Warning: Current enrollments ({current_enrollment_count}) exceed new capacity ({capacity_val}). "
                          "Enrollments will not be removed automatically. Adjust capacity carefully.")
                courses_df.loc[idx, 'Capacity'] = capacity_val
            except ValueError:
                print("Invalid capacity. Keeping current value.")

        save_data(courses_df, COURSES_SHEET)
        print(f"Course assignment {class_id_to_modify} updated successfully.")

    def manage_enrollments(self):
        """Admin manages student enrollments (add/remove), updating capacity."""
        enrollments_df = load_data(ENROLLMENTS_SHEET, ['StudentID', 'CourseID', 'ClassID']) 
        students_df = load_data(STUDENTS_SHEET, ['StudentID', 'StudentName', 'Password'])
        courses_df = load_data(COURSES_SHEET, ['ClassID', 'CourseID', 'CourseName', 'FacultyID', 'Capacity'])

        if students_df.empty:
            print("No students registered. Cannot manage enrollments.")
            return
        if courses_df.empty:
            print("No course assignments available. Cannot manage enrollments.")
            return

        print("\n--- Manage Student Enrollments ---")
        print("1. Add Student to Course Assignment")
        print("2. Remove Student from Course Assignment")
        print("3. View All Enrollments")
        choice = input("Enter choice: ")

        if choice == '1':
            student_id = input("Enter Student ID: ").strip().upper()
            if student_id not in students_df['StudentID'].values:
                print("Student ID not found.")
                return
            
            print("\n--- Available Course Assignments (with Remaining Seats) ---")
            display_courses_df = courses_df.copy()
            enrollment_counts = enrollments_df.groupby('ClassID').size().reset_index(name='EnrolledCount')
            display_courses_df = pd.merge(display_courses_df, enrollment_counts, on='ClassID', how='left')
            display_courses_df['EnrolledCount'] = display_courses_df['EnrolledCount'].fillna(0).astype(int)

            display_courses_df['Remaining Seats'] = display_courses_df.apply(lambda row: row['Capacity'] - row['EnrolledCount'] if row['Capacity'] > 0 else 'Unlimited', axis=1)
            
            faculty_df = load_data(FACULTY_SHEET, ['FacultyID', 'FacultyName', 'Password'])
            display_courses_df = pd.merge(display_courses_df, faculty_df[['FacultyID', 'FacultyName']], on='FacultyID', how='left')
            display_courses_df['FacultyName'] = display_courses_df['FacultyName'].fillna('N/A')

            print(display_courses_df[['ClassID', 'CourseID', 'CourseName', 'FacultyName', 'Capacity', 'Remaining Seats']].to_string(index=False))

            class_id = input("Enter Class ID to add student to: ").strip().upper()

            target_assignment = courses_df[courses_df['ClassID'] == class_id]
            if target_assignment.empty:
                print("Class ID not found.")
                return
            
            if not enrollments_df[(enrollments_df['StudentID'] == student_id) & 
                                  (enrollments_df['ClassID'] == class_id)].empty:
                print(f"{student_id} is already enrolled in Class {class_id}.")
                return
            
            assignment_idx = target_assignment.index[0]
            assignment_capacity = courses_df.loc[assignment_idx, 'Capacity']
            current_enrollment_count = enrollments_df[enrollments_df['ClassID'] == class_id].shape[0]

            if assignment_capacity > 0 and current_enrollment_count >= assignment_capacity:
                print(f"Sorry, Class {class_id} has reached its maximum capacity. Cannot add student.")
                return

            new_enrollment = pd.DataFrame([{'StudentID': student_id, 'CourseID': courses_df.loc[assignment_idx, 'CourseID'], 'ClassID': class_id}])
            enrollments_df = pd.concat([enrollments_df, new_enrollment], ignore_index=True)
            save_data(enrollments_df, ENROLLMENTS_SHEET)
            
            print(f"Enrollment added: {student_id} in Class {class_id}. Available capacity updated.")

        elif choice == '2':
            student_id = input("Enter Student ID: ").strip().upper()
            if student_id not in students_df['StudentID'].values:
                print("Student ID not found.")
                return
            
            student_enrollments = enrollments_df[enrollments_df['StudentID'] == student_id]
            if student_enrollments.empty:
                print(f"{student_id} has no enrollments to remove.")
                return
            
            print(f"\n--- Course Assignments {student_id} is Enrolled In ---")
            student_enrollment_details = pd.merge(student_enrollments, courses_df, on='ClassID', how='left')
            
            enrollment_counts = enrollments_df.groupby('ClassID').size().reset_index(name='Enrolled Count')
            student_enrollment_details = pd.merge(student_enrollment_details, enrollment_counts, on='ClassID', how='left')
            student_enrollment_details['Enrolled Count'] = student_enrollment_details['Enrolled Count'].fillna(0).astype(int)

            student_enrollment_details['Remaining Seats'] = student_enrollment_details.apply(lambda row: row['Capacity'] - row['Enrolled Count'] if row['Capacity'] > 0 else 'Unlimited', axis=1)

            faculty_df = load_data(FACULTY_SHEET, ['FacultyID', 'FacultyName', 'Password'])
            student_enrollment_details = pd.merge(student_enrollment_details, faculty_df[['FacultyID', 'FacultyName']], on='FacultyID', how='left')
            student_enrollment_details['FacultyName'] = student_enrollment_details['FacultyName'].fillna('N/A')

            print(student_enrollment_details[['ClassID', 'CourseID', 'CourseName', 'FacultyName', 'Capacity', 'Remaining Seats']].to_string(index=False))

            class_id = input("Enter Class ID to remove student from: ").strip().upper()
            
            if not ((enrollments_df['StudentID'] == student_id) & 
                    (enrollments_df['ClassID'] == class_id)).any():
                print(f"{student_id} is not enrolled in Class {class_id}.")
                return

            assignment_idx = courses_df[courses_df['ClassID'] == class_id].index[0]
            
            enrollments_df = enrollments_df[~((enrollments_df['StudentID'] == student_id) & 
                                              (enrollments_df['ClassID'] == class_id))]
            save_data(enrollments_df, ENROLLMENTS_SHEET)
            
            if courses_df.loc[assignment_idx, 'Capacity'] >= 0: 
                courses_df.loc[assignment_idx, 'Capacity'] += 1
                save_data(courses_df, COURSES_SHEET)
            print(f"Enrollment removed: {student_id} from Class {class_id}. Available capacity updated.")

        elif choice == '3':
            if not enrollments_df.empty:
                print("\n--- All Enrollments ---")
                merged_df = pd.merge(enrollments_df, courses_df[['ClassID', 'CourseID', 'CourseName']], 
                                     on='ClassID', how='left', suffixes=('_enrollment', ''))
                
                merged_df = pd.merge(merged_df, students_df[['StudentID', 'StudentName']], on='StudentID', how='left')
                print(merged_df[['StudentID', 'StudentName', 'CourseID', 'ClassID', 'CourseName']].to_string(index=False))
            else:
                print("No enrollments exist.")
        else:
            print("Invalid choice.")

    def view_all_faculty(self):
        """Admin views all faculty members."""
        faculty_df = load_data(FACULTY_SHEET, ['FacultyID', 'FacultyName', 'Password']) 
        if not faculty_df.empty:
            print("\n--- All Faculty ---")
            print(faculty_df[['FacultyID', 'FacultyName']].to_string(index=False))
        else:
            print("No faculty added yet.")

    def view_all_students(self):
        """Admin views all students."""
        students_df = load_data(STUDENTS_SHEET, ['StudentID', 'StudentName', 'Password']) 
        if not students_df.empty:
            print("\n--- All Students ---")
            print(students_df[['StudentID', 'StudentName']].to_string(index=False))
        else:
            print("No students added yet.")

    def view_all_courses(self):
        """Admin views all course assignments, including remaining seats and faculty."""
        courses_df = load_data(COURSES_SHEET, ['ClassID', 'CourseID', 'CourseName', 'FacultyID', 'Capacity'])
        enrollments_df = load_data(ENROLLMENTS_SHEET, ['StudentID', 'CourseID', 'ClassID'])
        faculty_df = load_data(FACULTY_SHEET, ['FacultyID', 'FacultyName', 'Password'])

        if not courses_df.empty:
            print("\n--- All Course Assignments ---")
            enrollment_counts = enrollments_df.groupby('ClassID').size().reset_index(name='EnrolledCount')
            
            display_df = pd.merge(courses_df, enrollment_counts, on='ClassID', how='left')
            display_df['EnrolledCount'] = display_df['EnrolledCount'].fillna(0).astype(int) 

            display_df['Remaining Seats'] = display_df.apply(
                lambda row: row['Capacity'] - row['EnrolledCount'] if row['Capacity'] > 0 else 'Unlimited', axis=1
            )
            
            display_df = pd.merge(display_df, faculty_df[['FacultyID', 'FacultyName']], on='FacultyID', how='left')
            display_df['FacultyName'] = display_df['FacultyName'].fillna('N/A')

            print(display_df[['ClassID', 'CourseID', 'CourseName', 'FacultyName', 'Capacity', 'Remaining Seats']].to_string(index=False))
        else:
            print("No course assignments available.")

# --- Faculty Class ---
class Faculty:
    def __init__(self, faculty_id):
        self.faculty_id = faculty_id
        faculty_df = load_data(FACULTY_SHEET, ['FacultyID', 'FacultyName', 'Password']) 
        self.faculty_name = faculty_df[faculty_df['FacultyID'] == faculty_id]['FacultyName'].iloc[0] if not faculty_df[faculty_df['FacultyID'] == faculty_id].empty else "Unknown"

    def check_assigned_courses(self):
        """Faculty checks course assignments assigned to them, including remaining seats."""
        courses_df = load_data(COURSES_SHEET, ['ClassID', 'CourseID', 'CourseName', 'FacultyID', 'Capacity'])
        enrollments_df = load_data(ENROLLMENTS_SHEET, ['StudentID', 'CourseID', 'ClassID'])
        faculty_df = load_data(FACULTY_SHEET, ['FacultyID', 'FacultyName', 'Password'])

        assigned_courses = courses_df[courses_df['FacultyID'] == self.faculty_id].copy()
        
        if not assigned_courses.empty:
            print(f"\n--- Course Assignments Assigned to Faculty {self.faculty_name} ({self.faculty_id}) ---")
            
            enrollment_counts = enrollments_df.groupby('ClassID').size().reset_index(name='EnrolledCount')
            
            display_df = pd.merge(assigned_courses, enrollment_counts, on='ClassID', how='left')
            display_df['EnrolledCount'] = display_df['EnrolledCount'].fillna(0).astype(int)

            display_df['Remaining Seats'] = display_df.apply(
                lambda row: row['Capacity'] - row['EnrolledCount'] if row['Capacity'] > 0 else 'Unlimited', axis=1
            )
            
            display_df = pd.merge(display_df, faculty_df[['FacultyID', 'FacultyName']], on='FacultyID', how='left')
            display_df['FacultyName'] = display_df['FacultyName'].fillna('N/A')

            print(display_df[['ClassID', 'CourseID', 'CourseName', 'FacultyName', 'Capacity', 'Remaining Seats']].to_string(index=False))
        else:
            print(f"No course assignments assigned to Faculty {self.faculty_name} ({self.faculty_id}).")

    def drop_and_assign_course(self):
        """Faculty drops one of their assigned courses by reassigning it to another faculty member."""
        courses_df = load_data(COURSES_SHEET, ['ClassID', 'CourseID', 'CourseName', 'FacultyID', 'Capacity'])
        faculty_df = load_data(FACULTY_SHEET, ['FacultyID', 'FacultyName', 'Password'])

        my_assigned_courses = courses_df[courses_df['FacultyID'] == self.faculty_id]

        if my_assigned_courses.empty:
            print(f"You ({self.faculty_name}) are not currently assigned to any courses.")
            return

        print(f"\n--- Your Assigned Courses ({self.faculty_name}) ---")
        merged_display_df = pd.merge(my_assigned_courses, faculty_df[['FacultyID', 'FacultyName']], on='FacultyID', how='left')
        print(merged_display_df[['ClassID', 'CourseID', 'CourseName', 'FacultyName']].to_string(index=False))

        class_id_to_reassign = input("Enter the Class ID of the course you wish to reassign: ").strip().upper()

        target_class_row = my_assigned_courses[my_assigned_courses['ClassID'] == class_id_to_reassign]

        if target_class_row.empty:
            print(f"Error: Class ID '{class_id_to_reassign}' not found or not assigned to you.")
            return

        idx_in_courses_df = courses_df[courses_df['ClassID'] == class_id_to_reassign].index[0]
        
        print("\n--- Available Faculty Members ---")
        other_faculty_df = faculty_df[faculty_df['FacultyID'] != self.faculty_id]
        if other_faculty_df.empty:
            print("No other faculty members available to reassign the course to.")
            return
        print(other_faculty_df[['FacultyID', 'FacultyName']].to_string(index=False))

        new_faculty_id = input("Enter the Faculty ID of the member to reassign this course to: ").strip().upper()

        if new_faculty_id not in faculty_df['FacultyID'].values:
            print(f"Error: Faculty ID '{new_faculty_id}' not found. Reassignment cancelled.")
            return

        old_faculty_name = self.faculty_name
        old_course_name = courses_df.loc[idx_in_courses_df, 'CourseName']
        new_faculty_name = faculty_df[faculty_df['FacultyID'] == new_faculty_id]['FacultyName'].iloc[0]

        courses_df.loc[idx_in_courses_df, 'FacultyID'] = new_faculty_id
        save_data(courses_df, COURSES_SHEET)

        print(f"Successfully reassigned '{old_course_name}' (ClassID: {class_id_to_reassign}) "
              f"from {old_faculty_name} ({self.faculty_id}) to {new_faculty_name} ({new_faculty_id}).")

    def check_enrolled_students(self):
        """Faculty checks students enrolled in their course assignments."""
        courses_df = load_data(COURSES_SHEET, ['ClassID', 'CourseID', 'CourseName', 'FacultyID', 'Capacity'])
        enrollments_df = load_data(ENROLLMENTS_SHEET, ['StudentID', 'CourseID', 'ClassID'])
        students_df = load_data(STUDENTS_SHEET, ['StudentID', 'StudentName', 'Password']) 

        assigned_courses = courses_df[courses_df['FacultyID'] == self.faculty_id]
        
        if assigned_courses.empty:
            print(f"No course assignments assigned to Faculty {self.faculty_name} ({self.faculty_id}) to check enrollments for.")
            return

        print(f"\n--- Enrolled Students in Course Assignments for Faculty {self.faculty_name} ({self.faculty_id}) ---")
        found_enrollments = False
        for _, course_row in assigned_courses.iterrows():
            class_id = course_row['ClassID']
            course_id = course_row['CourseID']
            course_name = course_row['CourseName']
            course_capacity = course_row['Capacity']
            
            students_in_assignment = enrollments_df[enrollments_df['ClassID'] == class_id]
            current_enrollment_count = students_in_assignment.shape[0]

            remaining_seats_str = f"Remaining Seats: {course_capacity - current_enrollment_count}" if course_capacity > 0 else "Remaining Seats: Unlimited"

            if not students_in_assignment.empty:
                found_enrollments = True
                print(f"\nCourse: {course_name} ({course_id}, Class {class_id}) - {remaining_seats_str}")
                print("  Enrolled Students:")
                enrolled_student_details = pd.merge(students_in_assignment, students_df, on='StudentID', how='left')
                for _, student_row in enrolled_student_details.iterrows():
                    print(f"    - {student_row['StudentID']} ({student_row['StudentName']})")
            else:
                print(f"\nCourse: {course_name} ({course_id}, Class {class_id}) - No students enrolled. ({remaining_seats_str})")
        
        if not found_enrollments and not assigned_courses.empty:
            print("No students enrolled in any of your assigned course assignments yet.")

# --- Student Class ---
class Student:
    def __init__(self, student_id):
        self.student_id = student_id
        students_df = load_data(STUDENTS_SHEET, ['StudentID', 'StudentName', 'Password']) 
        self.student_name = students_df[students_df['StudentID'] == student_id]['StudentName'].iloc[0] if not students_df[students_df['StudentID'] == student_id].empty else "Unknown"

    def enroll_course(self):
        """Student enrolls into a course by choosing a faculty, updating capacity."""
        courses_df = load_data(COURSES_SHEET, ['ClassID', 'CourseID', 'CourseName', 'FacultyID', 'Capacity'])
        enrollments_df = load_data(ENROLLMENTS_SHEET, ['StudentID', 'CourseID', 'ClassID'])
        faculty_df = load_data(FACULTY_SHEET, ['FacultyID', 'FacultyName', 'Password'])

        if courses_df.empty:
            print("No course assignments available for enrollment yet.")
            return

        print("\n--- Available Courses for Enrollment ---")
        
        unique_courses = courses_df['CourseID'].unique()
        if len(unique_courses) == 0:
            print("No courses available for enrollment.")
            return

        print("Please choose a Course ID from the list below:")
        for course_id in unique_courses:
            course_name = courses_df[courses_df['CourseID'] == course_id]['CourseName'].iloc[0]
            print(f"- {course_id} ({course_name})")

        course_id_to_enroll = input("Enter the Course ID you want to enroll in: ").strip().upper()
        
        available_assignments = courses_df[courses_df['CourseID'] == course_id_to_enroll].copy()
        
        if available_assignments.empty:
            print("Invalid Course ID or no assignments found for this course.")
            return

        enrollment_counts = enrollments_df.groupby('ClassID').size().reset_index(name='EnrolledCount')
        available_assignments = pd.merge(available_assignments, enrollment_counts, on='ClassID', how='left')
        available_assignments['EnrolledCount'] = available_assignments['EnrolledCount'].fillna(0).astype(int)
        
        available_assignments['Remaining Seats'] = available_assignments.apply(
            lambda row: row['Capacity'] - row['EnrolledCount'] if row['Capacity'] > 0 else 'Unlimited', axis=1
        )
        
        available_assignments = pd.merge(available_assignments, faculty_df[['FacultyID', 'FacultyName']], on='FacultyID', how='left')
        available_assignments['FacultyName'] = available_assignments['FacultyName'].fillna('N/A')

        eligible_assignments = available_assignments[
            (available_assignments['Capacity'] == 0) | 
            (available_assignments['Remaining Seats'] > 0)
        ]

        if eligible_assignments.empty:
            print(f"Sorry, all assignments for '{course_id_to_enroll}' are currently full or unavailable.")
            return
            
        print(f"\n--- Available Faculty for {course_id_to_enroll} ---")
        print(eligible_assignments[['ClassID', 'FacultyName', 'Capacity', 'Remaining Seats']].to_string(index=False))

        chosen_class_id = input("Enter the Class ID of the faculty you want to choose: ").strip().upper()

        target_assignment_row = courses_df[courses_df['ClassID'] == chosen_class_id] 
        
        if target_assignment_row.empty:
            print("Invalid Class ID or the chosen class is full. Please choose from the list.")
            return

        assignment_idx = target_assignment_row.index[0]

        if not enrollments_df[(enrollments_df['StudentID'] == self.student_id) & 
                              (enrollments_df['ClassID'] == chosen_class_id)].empty:
            print(f"You are already enrolled in this class ({chosen_class_id}).")
            return

        assignment_capacity = courses_df.loc[assignment_idx, 'Capacity'] 

        current_enrollment_count = enrollments_df[enrollments_df['ClassID'] == chosen_class_id].shape[0]

        if assignment_capacity > 0 and current_enrollment_count >= assignment_capacity:
            print(f"Sorry, this class ({chosen_class_id}) has reached its maximum capacity. No seats remaining.")
            return

        new_enrollment = pd.DataFrame([{'StudentID': self.student_id, 'CourseID': course_id_to_enroll, 'ClassID': chosen_class_id}])
        enrollments_df = pd.concat([enrollments_df, new_enrollment], ignore_index=True)
        save_data(enrollments_df, ENROLLMENTS_SHEET)
        
        enrolled_course_name = courses_df.loc[assignment_idx, 'CourseName']
        enrolled_faculty_id = courses_df.loc[assignment_idx, 'FacultyID']

        faculty_df_current = load_data(FACULTY_SHEET, ['FacultyID', 'FacultyName', 'Password']) 
        enrolled_faculty_name = faculty_df_current[faculty_df_current['FacultyID'] == enrolled_faculty_id]['FacultyName'].iloc[0] if enrolled_faculty_id in faculty_df_current['FacultyID'].values else "Unknown"

        print(f"Successfully enrolled '{self.student_name}' ({self.student_id}) in '{enrolled_course_name}' "
              f"with Faculty {enrolled_faculty_name} (ClassID: {chosen_class_id}). Available capacity updated.")
    
    def drop_course(self):
        """Student drops an enrolled course."""
        enrollments_df = load_data(ENROLLMENTS_SHEET, ['StudentID', 'CourseID', 'ClassID'])
        courses_df = load_data(COURSES_SHEET, ['ClassID', 'CourseID', 'CourseName', 'FacultyID', 'Capacity'])

        my_enrollments = enrollments_df[enrollments_df['StudentID'] == self.student_id]

        if my_enrollments.empty:
            print(f"You ({self.student_name}) are not currently enrolled in any courses.")
            return

        print(f"\n--- Your Currently Enrolled Courses ({self.student_name}) ---")

        merged_display_df = pd.merge(my_enrollments, courses_df[['ClassID', 'CourseID', 'CourseName']], on='ClassID', how='left')
        print(merged_display_df[['ClassID', 'CourseID', 'CourseName']].to_string(index=False))

        class_id_to_drop = input("Enter the Class ID of the course you wish to drop: ").strip().upper()

        enrollment_to_drop = my_enrollments[my_enrollments['ClassID'] == class_id_to_drop]

        if enrollment_to_drop.empty:
            print(f"Error: You are not enrolled in Class ID '{class_id_to_drop}'.")
            return

        target_course_in_courses_df = courses_df[courses_df['ClassID'] == class_id_to_drop]
        if target_course_in_courses_df.empty:
            print(f"Error: Course data for Class ID '{class_id_to_drop}' not found. Cannot update capacity.")
            return

        course_idx = target_course_in_courses_df.index[0]
        course_name = courses_df.loc[course_idx, 'CourseName']
        course_capacity = courses_df.loc[course_idx, 'Capacity']

        enrollments_df = enrollments_df[~((enrollments_df['StudentID'] == self.student_id) &
                                          (enrollments_df['ClassID'] == class_id_to_drop))]
        save_data(enrollments_df, ENROLLMENTS_SHEET)

        # if course_capacity > 0:
        #     courses_df.loc[course_idx, 'Capacity'] += 1
        #     save_data(courses_df, COURSES_SHEET)

        print(f"Successfully dropped '{course_name}' (ClassID: {class_id_to_drop}). Capacity updated.")

    def swap_course(self):
        """Student swaps one enrolled course for another."""
        enrollments_df = load_data(ENROLLMENTS_SHEET, ['StudentID', 'CourseID', 'ClassID'])
        courses_df = load_data(COURSES_SHEET, ['ClassID', 'CourseID', 'CourseName', 'FacultyID', 'Capacity'])
        faculty_df = load_data(FACULTY_SHEET, ['FacultyID', 'FacultyName', 'Password'])

        my_enrollments = enrollments_df[enrollments_df['StudentID'] == self.student_id]

        if my_enrollments.empty:
            print(f"You ({self.student_name}) are not currently enrolled in any courses to swap.")
            return

        # --- Step 1: Choose Course to Drop ---
        print(f"\n--- Your Currently Enrolled Courses ({self.student_name}) ---")
        merged_display_df = pd.merge(my_enrollments, courses_df[['ClassID', 'CourseID', 'CourseName']], on='ClassID', how='left')
        print(merged_display_df[['ClassID', 'CourseID', 'CourseName']].to_string(index=False))

        class_id_to_drop = input("Enter the Class ID of the course you wish to DROP (to make space for a new one): ").strip().upper()

        enrollment_to_drop_idx = my_enrollments[(my_enrollments['StudentID'] == self.student_id) &
                                                (my_enrollments['ClassID'] == class_id_to_drop)].index

        if enrollment_to_drop_idx.empty:
            print(f"Error: You are not enrolled in Class ID '{class_id_to_drop}'. Swap cancelled.")
            return

        # Get details of the course to be dropped
        old_course_details = courses_df[courses_df['ClassID'] == class_id_to_drop]
        if old_course_details.empty:
            print(f"Error: Course data for Class ID '{class_id_to_drop}' not found. Swap cancelled.")
            return
        
        old_course_idx = old_course_details.index[0]
        old_course_name = old_course_details.loc[old_course_idx, 'CourseName']
        old_course_capacity = old_course_details.loc[old_course_idx, 'Capacity']


        # --- Step 2: Choose Course to Enroll In ---
        print("\n--- Available Courses for Enrollment (for the swap) ---")
        unique_courses = courses_df['CourseID'].unique()
        if len(unique_courses) == 0:
            print("No courses available for enrollment.")
            return

        print("Please choose a Course ID from the list below:")
        for course_id in unique_courses:
            course_name = courses_df[courses_df['CourseID'] == course_id]['CourseName'].iloc[0]
            print(f"- {course_id} ({course_name})")

        new_course_id = input("Enter the Course ID for the NEW course you want to enroll in: ").strip().upper()

        available_assignments = courses_df[courses_df['CourseID'] == new_course_id].copy()
        
        if available_assignments.empty:
            print("Invalid NEW Course ID or no assignments found for this course. Swap cancelled.")
            return

        # Filter out the course being dropped from available assignments to prevent re-enrolling in it
        available_assignments = available_assignments[available_assignments['ClassID'] != class_id_to_drop]
        
        # Calculate current enrollments for each assignment
        enrollment_counts = enrollments_df.groupby('ClassID').size().reset_index(name='EnrolledCount')
        available_assignments = pd.merge(available_assignments, enrollment_counts, on='ClassID', how='left')
        available_assignments['EnrolledCount'] = available_assignments['EnrolledCount'].fillna(0).astype(int)
        
        available_assignments['Remaining Seats'] = available_assignments.apply(
            lambda row: row['Capacity'] - row['EnrolledCount'] if row['Capacity'] > 0 else 'Unlimited', axis=1
        )
        
        available_assignments = pd.merge(available_assignments, faculty_df[['FacultyID', 'FacultyName']], on='FacultyID', how='left')
        available_assignments['FacultyName'] = available_assignments['FacultyName'].fillna('N/A')

        eligible_assignments = available_assignments[
            (available_assignments['Capacity'] == 0) | 
            (available_assignments['Remaining Seats'] > 0)
        ]

        if eligible_assignments.empty:
            print(f"Sorry, all assignments for '{new_course_id}' are currently full or unavailable. Swap cancelled.")
            return
            
        print(f"\n--- Available Faculty for {new_course_id} ---")
        print(eligible_assignments[['ClassID', 'FacultyName', 'Capacity', 'Remaining Seats']].to_string(index=False))

        new_class_id = input("Enter the Class ID of the NEW faculty you want to choose for enrollment: ").strip().upper()

        new_target_assignment_row = courses_df[courses_df['ClassID'] == new_class_id]
        
        if new_target_assignment_row.empty:
            print("Invalid NEW Class ID. Swap cancelled.")
            return

        new_assignment_idx = new_target_assignment_row.index[0]
        new_assignment_capacity = courses_df.loc[new_assignment_idx, 'Capacity']
        
        # Check if already enrolled in the new class
        if not enrollments_df[(enrollments_df['StudentID'] == self.student_id) & 
                              (enrollments_df['ClassID'] == new_class_id)].empty:
            print(f"You are already enrolled in the new class ({new_class_id}). Swap cancelled.")
            return

        # Check capacity for the new class (considering *current* enrollments before the drop)
        current_enrollment_new_class = enrollments_df[enrollments_df['ClassID'] == new_class_id].shape[0]

        if new_assignment_capacity > 0 and current_enrollment_new_class >= new_assignment_capacity:
            print(f"Sorry, the new class ({new_class_id}) is full. Cannot swap. Swap cancelled.")
            return
        
        # --- Step 3: Perform the Atomic Swap ---
        try:
            # 1. Temporarily drop the old course (in memory first, then save)
            temp_enrollments_df = enrollments_df.drop(enrollment_to_drop_idx)
            
            # 2. Add the new enrollment (in memory)
            new_enrollment = pd.DataFrame([{'StudentID': self.student_id, 'CourseID': new_course_id, 'ClassID': new_class_id}])
            temp_enrollments_df = pd.concat([temp_enrollments_df, new_enrollment], ignore_index=True)

            # 3. Update capacities (in memory)
            temp_courses_df = courses_df.copy()
            if old_course_capacity > 0:
                temp_courses_df.loc[old_course_idx, 'Capacity'] += 1 # Increase capacity for dropped course

            if new_assignment_capacity > 0:
                temp_courses_df.loc[new_assignment_idx, 'Capacity'] -= 1 # Decrease capacity for new course

            # 4. Save changes only if all steps were successful in memory
            save_data(temp_enrollments_df, ENROLLMENTS_SHEET)
            save_data(temp_courses_df, COURSES_SHEET)

            new_course_name_display = courses_df.loc[new_assignment_idx, 'CourseName']
            print(f"Successfully swapped '{old_course_name}' (ClassID: {class_id_to_drop}) "
                  f"for '{new_course_name_display}' (ClassID: {new_class_id}). Capacities updated.")

        except Exception as e:
            print(f"An error occurred during the swap: {e}. No changes were saved.")

    def view_my_courses(self):
        """Student views their enrolled course assignments, including faculty."""
        enrollments_df = load_data(ENROLLMENTS_SHEET, ['StudentID', 'CourseID', 'ClassID']) 
        courses_df = load_data(COURSES_SHEET, ['ClassID', 'CourseID', 'CourseName', 'FacultyID', 'Capacity']) 
        faculty_df = load_data(FACULTY_SHEET, ['FacultyID', 'FacultyName', 'Password']) 

        my_enrollments = enrollments_df[enrollments_df['StudentID'] == self.student_id]

        if not my_enrollments.empty:
            print(f"\n--- Course Assignments Enrolled by {self.student_name} ({self.student_id}) ---")
            

            merged_df = pd.merge(my_enrollments, courses_df, on='ClassID', how='left', suffixes=('_enrollment', ''))


            merged_df = pd.merge(merged_df, faculty_df[['FacultyID', 'FacultyName']], on='FacultyID', how='left')
            
            enrollment_counts = enrollments_df.groupby('ClassID').size().reset_index(name='EnrolledCount')
            merged_df = pd.merge(merged_df, enrollment_counts, on='ClassID', how='left')
            merged_df['EnrolledCount'] = merged_df['EnrolledCount'].fillna(0).astype(int)

            merged_df['Remaining Seats'] = merged_df.apply(
                lambda row: row['Capacity'] - row['EnrolledCount'] if row['Capacity'] > 0 else 'Unlimited', axis=1
            )
            merged_df['FacultyName'] = merged_df['FacultyName'].fillna('N/A')

            print(merged_df[['ClassID', 'CourseID', 'CourseName', 'FacultyName', 'Capacity', 'Remaining Seats']].to_string(index=False))
        else:
            print(f"No course assignments enrolled by {self.student_name} ({self.student_id}) yet.")

# --- Main Program Loop ---

def main_menu():
    """Main menu for selecting user role and handling login."""
    print("--- Welcome to the Course Registration System ---")
    
    passwords_df = load_data(PASSWORDS_SHEET, ['UserID', 'Password'])
    if "ADMIN" not in passwords_df['UserID'].values:
        print("Adding default ADMIN user...")
        new_admin = pd.DataFrame([{'UserID': 'ADMIN', 'Password': 'adminpass'}])
        passwords_df = pd.concat([passwords_df, new_admin], ignore_index=True)
        save_data(passwords_df, PASSWORDS_SHEET)

    while True:
        print("\n--- Select User Role ---")
        print("1. Student")
        print("2. Faculty")
        print("3. Admin")
        print("4. Exit")
        
        user_role_choice = input("Enter your choice: ")

        if user_role_choice == '3':
            password = input("Enter Admin Password: ").strip()
            if authenticate_admin_misc("ADMIN", password):
                admin_obj = Admin()
                while True:
                    print("\n--- Admin Menu ---")
                    print("1. Add New Faculty")
                    print("2. Add New Student")
                    print("3. Create New Course Assignment")
                    print("4. Modify Existing Course Assignment")
                    print("5. Manage Student Enrollments")
                    print("6. View All Faculty")
                    print("7. View All Students")
                    print("8. View All Course Assignments")
                    print("9. Logout")
                    admin_choice = input("Enter your choice: ")

                    if admin_choice == '1':
                        admin_obj.add_new_faculty()
                    elif admin_choice == '2':
                        admin_obj.add_new_student()
                    elif admin_choice == '3':
                        admin_obj.create_course_assignment()
                    elif admin_choice == '4':
                        admin_obj.modify_course_assignment()
                    elif admin_choice == '5':
                        admin_obj.manage_enrollments()
                    elif admin_choice == '6':
                        admin_obj.view_all_faculty()
                    elif admin_choice == '7':
                        admin_obj.view_all_students()
                    elif admin_choice == '8':
                        admin_obj.view_all_courses()
                    elif admin_choice == '9':
                        print("Logging out...")
                        break
                    else:
                        print("Invalid choice. Please try again.")
            else:
                print("Admin login failed. Access denied.")

        elif user_role_choice == '2':
            faculty_id = input("Enter your Faculty ID: ").strip().upper()
            password = input("Enter Faculty Password: ").strip()
            if authenticate_faculty_student(faculty_id, password, 'faculty'):
                faculty_df = load_data(FACULTY_SHEET, ['FacultyID', 'FacultyName', 'Password'])
                if faculty_id not in faculty_df['FacultyID'].values: 
                    print("Error: Faculty ID not found after successful password verification. Data inconsistency.")
                    continue
                faculty_obj = Faculty(faculty_id)
                while True:
                    print(f"\n--- Faculty Menu ({faculty_obj.faculty_name} - {faculty_obj.faculty_id}) ---")
                    print("1. Check Assigned Course Assignments")
                    print("2. Check Enrolled Students in My Course Assignments")
                    print("3. Reassign/Drop a Course")
                    print("4. LOgout")
                    faculty_choice = input("Enter your choice: ")

                    if faculty_choice == '1':
                        faculty_obj.check_assigned_courses()
                    elif faculty_choice == '2':
                        faculty_obj.check_enrolled_students()
                    elif faculty_choice == '3': 
                        faculty_obj.drop_and_assign_course()
                    elif faculty_choice == '4':
                        print("Logging out...")
                        break
                    else:
                        print("Invalid choice. Please try again.")
            else:
                print("Faculty login failed. Access denied.")

        elif user_role_choice == '1':
            student_id = input("Enter your Student ID: ").strip().upper()
            password = input("Enter Student Password: ").strip()
            if authenticate_faculty_student(student_id, password, 'student'):
                students_df = load_data(STUDENTS_SHEET, ['StudentID', 'StudentName', 'Password'])
                if student_id not in students_df['StudentID'].values: 
                    print("Error: Student ID not found after successful password verification. Data inconsistency.")
                    continue
                student_obj = Student(student_id)
                while True:
                    print(f"\n--- Student Menu ({student_obj.student_name} - {student_obj.student_id}) ---")
                    print("1. Enroll in a Course")
                    print("2. View My Enrolled Courses")
                    print("3. Drop a Course") 
                    print("4. Swap Courses")
                    print("5. Logout")
                    student_choice = input("Enter your choice: ")

                    if student_choice == '1':
                        student_obj.enroll_course()
                    elif student_choice == '2':
                        student_obj.view_my_courses()
                    elif student_choice == '3': 
                        student_obj.drop_course()
                    elif student_choice == '4': 
                        student_obj.swap_course()
                    elif student_choice == '5':
                        print("Logging out...")
                        break
                    else:
                        print("Invalid choice. Please try again.")
            else:
                print("Student login failed. Access denied.")

        elif user_role_choice == '4':
            print("Closing system.....")
            break
        else:
            print("Invalid choice. Please enter 1, 2, 3, or 4.")

if __name__ == "__main__":
    main_menu()