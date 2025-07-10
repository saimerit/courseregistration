import pandas as pd
import os

# --- File Paths ---
COURSES_FILE = r'C:\college despktop\CODING\SE\LAB1-coursereg\courses.csv'
FACULTY_FILE = r'C:\college despktop\CODING\SE\LAB1-coursereg\faculty.csv'
STUDENTS_FILE = r'C:\college despktop\CODING\SE\LAB1-coursereg\students.csv'
ENROLLMENTS_FILE = r'C:\college despktop\CODING\SE\LAB1-coursereg\enrollments.csv'
PASSWORDS_FILE = r"C:\college despktop\CODING\SE\LAB1-coursereg\passwords.csv" 

# --- Helper Functions for Data Loading/Saving ---

def load_data(file_path, columns):
    """Loads data from a CSV file. Creates an empty DataFrame if the file doesn't exist."""
    if not os.path.exists(file_path):
        print(f"Creating empty {file_path}...")
        df = pd.DataFrame(columns=columns)
        save_data(df, file_path) # Save empty DataFrame to create the file
        return df
    return pd.read_csv(file_path)

def save_data(df, file_path):
    """Saves data to a CSV file."""
    df.to_csv(file_path, index=False)

def authenticate_admin_misc(user_id, password):
    """Authenticates Admin or other miscellaneous users against passwords.csv."""
    passwords_df = load_data(PASSWORDS_FILE, ['UserID', 'Password'])
    
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
    """Authenticates a Faculty or Student user against their respective CSV files."""
    if user_type == 'faculty':
        user_df = load_data(FACULTY_FILE, ['FacultyID', 'FacultyName', 'Password'])
        id_col = 'FacultyID'
    elif user_type == 'student':
        user_df = load_data(STUDENTS_FILE, ['StudentID', 'StudentName', 'Password'])
        id_col = 'StudentID'
    else:
        return False # Should not happen, invalid user_type
    
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
        faculty_df = load_data(FACULTY_FILE, ['FacultyID', 'FacultyName', 'Password'])
        
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
        save_data(faculty_df, FACULTY_FILE)
        print(f"Faculty '{faculty_name}' ({faculty_id}) added successfully.")

    def add_new_student(self):
        """Admin adds a new student with password."""
        students_df = load_data(STUDENTS_FILE, ['StudentID', 'StudentName', 'Password'])
        
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
        save_data(students_df, STUDENTS_FILE)
        print(f"Student '{student_name}' ({student_id}) added successfully.")

    def create_course(self):
        """Admin creates a new course and assigns it to faculty."""
        courses_df = load_data(COURSES_FILE, ['CourseID', 'CourseName', 'FacultyID', 'Capacity'])
        
        course_id = input("Enter new Course ID (e.g., CS101): ").strip().upper()
        if course_id in courses_df['CourseID'].values:
            print("Course ID already exists. Please use a unique ID.")
            return

        course_name = input("Enter Course Name: ").strip()
        faculty_id = input("Enter Faculty ID to assign this course (e.g., F001): ").strip().upper()

        faculty_df = load_data(FACULTY_FILE, ['FacultyID', 'FacultyName', 'Password'])
        if faculty_id not in faculty_df['FacultyID'].values:
            print(f"Warning: Faculty ID '{faculty_id}' does not exist. Course created anyway, but assign to an existing faculty for proper functionality.")
        
        capacity = input("Enter course capacity (e.g., 50, leave blank for no limit): ")
        try:
            capacity = int(capacity) if capacity else 0
        except ValueError:
            print("Invalid capacity. Setting to default 0 (no limit).")
            capacity = 0

        new_course = pd.DataFrame([{
            'CourseID': course_id,
            'CourseName': course_name,
            'FacultyID': faculty_id,
            'Capacity': capacity
        }])
        courses_df = pd.concat([courses_df, new_course], ignore_index=True)
        save_data(courses_df, COURSES_FILE)
        print(f"Course '{course_name}' ({course_id}) assigned to Faculty {faculty_id} successfully.")

    def modify_course(self):
        """Admin modifies an existing course."""
        courses_df = load_data(COURSES_FILE, ['CourseID', 'CourseName', 'FacultyID', 'Capacity'])
        
        if courses_df.empty:
            print("No courses to modify.")
            return

        print("\n--- Current Courses ---")
        # Display Remaining Seats here for clarity when modifying
        enrollments_df = load_data(ENROLLMENTS_FILE, ['StudentID', 'CourseID'])
        display_df = courses_df.copy()
        
        display_df['Enrolled'] = display_df['CourseID'].apply(lambda cid: enrollments_df[enrollments_df['CourseID'] == cid].shape[0])
        display_df['Remaining Seats'] = display_df.apply(lambda row: row['Capacity'] - row['Enrolled'] if row['Capacity'] > 0 else 'N/A', axis=1)
        
        print(display_df[['CourseID', 'CourseName', 'FacultyID', 'Capacity', 'Remaining Seats']].to_string(index=False))

        course_id_to_modify = input("Enter Course ID to modify: ").strip().upper()

        if course_id_to_modify not in courses_df['CourseID'].values:
            print("Course ID not found.")
            return

        idx = courses_df[courses_df['CourseID'] == course_id_to_modify].index[0]

        print(f"Modifying Course: {course_id_to_modify} - {courses_df.loc[idx, 'CourseName']}")
        
        new_name = input(f"Enter new Course Name (current: {courses_df.loc[idx, 'CourseName']}), press Enter to keep current: ").strip()
        if new_name:
            courses_df.loc[idx, 'CourseName'] = new_name

        new_faculty_id = input(f"Enter new Faculty ID (current: {courses_df.loc[idx, 'FacultyID']}), press Enter to keep current: ").strip().upper()
        if new_faculty_id:
            faculty_df = load_data(FACULTY_FILE, ['FacultyID', 'FacultyName', 'Password'])
            if new_faculty_id not in faculty_df['FacultyID'].values:
                print(f"Warning: New Faculty ID '{new_faculty_id}' does not exist. Assigning anyway.")
            courses_df.loc[idx, 'FacultyID'] = new_faculty_id

        new_capacity = input(f"Enter new Capacity (current: {courses_df.loc[idx, 'Capacity']}), press Enter to keep current: ").strip()
        if new_capacity:
            try:
                capacity_val = int(new_capacity)
                # Before setting new capacity, check if current enrollments exceed new capacity
                current_enrollment_count = enrollments_df[enrollments_df['CourseID'] == course_id_to_modify].shape[0]
                if capacity_val > 0 and current_enrollment_count > capacity_val:
                    print(f"Warning: Current enrollments ({current_enrollment_count}) exceed new capacity ({capacity_val}). "
                          "Enrollments will not be removed automatically. Adjust capacity carefully.")
                courses_df.loc[idx, 'Capacity'] = capacity_val
            except ValueError:
                print("Invalid capacity. Keeping current value.")

        save_data(courses_df, COURSES_FILE)
        print(f"Course {course_id_to_modify} updated successfully.")

    def manage_enrollments(self):
        """Admin manages student enrollments (add/remove), updating capacity."""
        enrollments_df = load_data(ENROLLMENTS_FILE, ['StudentID', 'CourseID'])
        students_df = load_data(STUDENTS_FILE, ['StudentID', 'StudentName', 'Password'])
        courses_df = load_data(COURSES_FILE, ['CourseID', 'CourseName', 'FacultyID', 'Capacity'])

        if students_df.empty:
            print("No students registered. Cannot manage enrollments.")
            return
        if courses_df.empty:
            print("No courses available. Cannot manage enrollments.")
            return

        print("\n--- Manage Student Enrollments ---")
        print("1. Add Course to Student")
        print("2. Remove Course from Student")
        print("3. View All Enrollments")
        choice = input("Enter choice: ")

        if choice == '1':
            student_id = input("Enter Student ID: ").strip().upper()
            if student_id not in students_df['StudentID'].values:
                print("Student ID not found.")
                return
            
            print("\n--- Available Courses (with Remaining Seats) ---")
            display_courses_df = courses_df.copy()
            display_courses_df['Enrolled'] = display_courses_df['CourseID'].apply(lambda cid: enrollments_df[enrollments_df['CourseID'] == cid].shape[0])
            display_courses_df['Remaining Seats'] = display_courses_df.apply(lambda row: row['Capacity'] - row['Enrolled'] if row['Capacity'] > 0 else 'N/A', axis=1)
            print(display_courses_df[['CourseID', 'CourseName', 'Capacity', 'Remaining Seats']].to_string(index=False))

            course_id = input("Enter Course ID to add: ").strip().upper()
            if course_id not in courses_df['CourseID'].values:
                print("Course ID not found.")
                return
            
            # Check for duplicate enrollment
            if not enrollments_df[(enrollments_df['StudentID'] == student_id) & (enrollments_df['CourseID'] == course_id)].empty:
                print(f"{student_id} is already enrolled in {course_id}.")
                return
            
            # Capacity check
            course_idx = courses_df[courses_df['CourseID'] == course_id].index[0]
            course_capacity = courses_df.loc[course_idx, 'Capacity']
            current_enrollment_count = enrollments_df[enrollments_df['CourseID'] == course_id].shape[0]

            if course_capacity > 0 and current_enrollment_count >= course_capacity:
                print(f"Sorry, {course_id} has reached its maximum capacity. Cannot add student.")
                return

            new_enrollment = pd.DataFrame([{'StudentID': student_id, 'CourseID': course_id}])
            enrollments_df = pd.concat([enrollments_df, new_enrollment], ignore_index=True)
            save_data(enrollments_df, ENROLLMENTS_FILE)
            
            # # Update capacity - Decrement available slots
            # if course_capacity > 0: # Only decrement if capacity is limited (>0)
            #     courses_df.loc[course_idx, 'Capacity'] -= 1
            #     save_data(courses_df, COURSES_FILE)
            print(f"Enrollment added: {student_id} in {course_id}. Available capacity updated.")

        elif choice == '2':
            student_id = input("Enter Student ID: ").strip().upper()
            if student_id not in students_df['StudentID'].values:
                print("Student ID not found.")
                return
            
            student_enrollments = enrollments_df[enrollments_df['StudentID'] == student_id]
            if student_enrollments.empty:
                print(f"{student_id} has no enrollments to remove.")
                return
            
            print(f"\n--- Courses {student_id} is Enrolled In ---")
            # Display Remaining Seats here for clarity when removing
            student_enrollment_courses = pd.merge(student_enrollments, courses_df, on='CourseID', how='left')
            
            student_enrollment_courses['Enrolled Count'] = student_enrollment_courses['CourseID'].apply(lambda cid: enrollments_df[enrollments_df['CourseID'] == cid].shape[0])
            student_enrollment_courses['Remaining Seats'] = student_enrollment_courses.apply(lambda row: row['Capacity'] - row['Enrolled Count'] if row['Capacity'] > 0 else 'N/A', axis=1)

            print(student_enrollment_courses[['CourseID', 'CourseName', 'Capacity', 'Remaining Seats']].to_string(index=False))

            course_id = input("Enter Course ID to remove: ").strip().upper()
            
            if not ((enrollments_df['StudentID'] == student_id) & (enrollments_df['CourseID'] == course_id)).any():
                print(f"{student_id} is not enrolled in {course_id}.")
                return

            # Before removing, get course index for capacity update
            course_idx = courses_df[courses_df['CourseID'] == course_id].index[0]
            
            enrollments_df = enrollments_df[~((enrollments_df['StudentID'] == student_id) & (enrollments_df['CourseID'] == course_id))]
            save_data(enrollments_df, ENROLLMENTS_FILE)
            
            # Update capacity - Increment available slots (if it was a limited course)
            if courses_df.loc[course_idx, 'Capacity'] >= 0: # Only increment if capacity is limited or set to 0 (meaning no limit or a specific number)
                courses_df.loc[course_idx, 'Capacity'] += 1
                save_data(courses_df, COURSES_FILE)
            print(f"Enrollment removed: {student_id} from {course_id}. Available capacity updated.")

        elif choice == '3':
            if not enrollments_df.empty:
                print("\n--- All Enrollments ---")
                merged_df = pd.merge(enrollments_df, courses_df[['CourseID', 'CourseName']], on='CourseID', how='left')
                merged_df = pd.merge(merged_df, students_df[['StudentID', 'StudentName']], on='StudentID', how='left')
                print(merged_df[['StudentID', 'StudentName', 'CourseID', 'CourseName']].to_string(index=False))
            else:
                print("No enrollments exist.")
        else:
            print("Invalid choice.")

    def view_all_faculty(self):
        """Admin views all faculty members."""
        faculty_df = load_data(FACULTY_FILE, ['FacultyID', 'FacultyName', 'Password']) 
        if not faculty_df.empty:
            print("\n--- All Faculty ---")
            print(faculty_df[['FacultyID', 'FacultyName']].to_string(index=False))
        else:
            print("No faculty added yet.")

    def view_all_students(self):
        """Admin views all students."""
        students_df = load_data(STUDENTS_FILE, ['StudentID', 'StudentName', 'Password']) 
        if not students_df.empty:
            print("\n--- All Students ---")
            print(students_df[['StudentID', 'StudentName']].to_string(index=False))
        else:
            print("No students added yet.")

    def view_all_courses(self):
        """Admin views all courses, including remaining seats."""
        courses_df = load_data(COURSES_FILE, ['CourseID', 'CourseName', 'FacultyID', 'Capacity'])
        enrollments_df = load_data(ENROLLMENTS_FILE, ['StudentID', 'CourseID'])

        if not courses_df.empty:
            print("\n--- All Courses ---")
            # Calculate current enrollments for each course
            enrollment_counts = enrollments_df.groupby('CourseID').size().reset_index(name='EnrolledCount')
            
            # Merge with courses_df
            display_df = pd.merge(courses_df, enrollment_counts, on='CourseID', how='left')
            display_df['EnrolledCount'] = display_df['EnrolledCount'].fillna(0).astype(int) # Fill NaN with 0 for courses with no enrollments

            # Calculate remaining seats
            # If Capacity is 0, it means unlimited, so show 'N/A' or 'Unlimited'
            display_df['Remaining Seats'] = display_df.apply(
                lambda row: row['Capacity'] - row['EnrolledCount'] if row['Capacity'] > 0 else 'Unlimited', axis=1
            )
            
            # Display desired columns
            print(display_df[['CourseID', 'CourseName', 'FacultyID', 'Capacity', 'Remaining Seats']].to_string(index=False))
            
        else:
            print("No courses available.")

# --- Faculty Class ---
class Faculty:
    def __init__(self, faculty_id):
        self.faculty_id = faculty_id
        faculty_df = load_data(FACULTY_FILE, ['FacultyID', 'FacultyName', 'Password']) 
        self.faculty_name = faculty_df[faculty_df['FacultyID'] == faculty_id]['FacultyName'].iloc[0] if not faculty_df[faculty_df['FacultyID'] == faculty_id].empty else "Unknown"

    def check_assigned_courses(self):
        """Faculty checks courses assigned to them, including remaining seats."""
        courses_df = load_data(COURSES_FILE, ['CourseID', 'CourseName', 'FacultyID', 'Capacity'])
        enrollments_df = load_data(ENROLLMENTS_FILE, ['StudentID', 'CourseID'])

        assigned_courses = courses_df[courses_df['FacultyID'] == self.faculty_id].copy()
        
        if not assigned_courses.empty:
            print(f"\n--- Courses Assigned to Faculty {self.faculty_name} ({self.faculty_id}) ---")
            
            # Calculate current enrollments for each assigned course
            enrollment_counts = enrollments_df.groupby('CourseID').size().reset_index(name='EnrolledCount')
            
            # Merge with assigned_courses
            display_df = pd.merge(assigned_courses, enrollment_counts, on='CourseID', how='left')
            display_df['EnrolledCount'] = display_df['EnrolledCount'].fillna(0).astype(int)

            # Calculate remaining seats
            display_df['Remaining Seats'] = display_df.apply(
                lambda row: row['Capacity'] - row['EnrolledCount'] if row['Capacity'] > 0 else 'Unlimited', axis=1
            )
            
            print(display_df[['CourseID', 'CourseName', 'Capacity', 'Remaining Seats']].to_string(index=False))
        else:
            print(f"No courses assigned to Faculty {self.faculty_name} ({self.faculty_id}).")

    def check_enrolled_students(self):
        """Faculty checks students enrolled in their courses."""
        courses_df = load_data(COURSES_FILE, ['CourseID', 'CourseName', 'FacultyID', 'Capacity'])
        enrollments_df = load_data(ENROLLMENTS_FILE, ['StudentID', 'CourseID'])
        students_df = load_data(STUDENTS_FILE, ['StudentID', 'StudentName', 'Password']) 

        assigned_courses = courses_df[courses_df['FacultyID'] == self.faculty_id]
        
        if assigned_courses.empty:
            print(f"No courses assigned to Faculty {self.faculty_name} ({self.faculty_id}) to check enrollments for.")
            return

        print(f"\n--- Enrolled Students in Courses for Faculty {self.faculty_name} ({self.faculty_id}) ---")
        found_enrollments = False
        for _, course_row in assigned_courses.iterrows():
            course_id = course_row['CourseID']
            course_name = course_row['CourseName']
            course_capacity = course_row['Capacity']
            
            students_in_course = enrollments_df[enrollments_df['CourseID'] == course_id]
            current_enrollment_count = students_in_course.shape[0]

            remaining_seats_str = f"Remaining Seats: {course_capacity - current_enrollment_count}" if course_capacity > 0 else "Remaining Seats: Unlimited"

            if not students_in_course.empty:
                found_enrollments = True
                print(f"\nCourse: {course_name} ({course_id}) - {remaining_seats_str}")
                print("  Enrolled Students:")
                enrolled_student_details = pd.merge(students_in_course, students_df, on='StudentID', how='left')
                for _, student_row in enrolled_student_details.iterrows():
                    print(f"    - {student_row['StudentID']} ({student_row['StudentName']})")
            else:
                print(f"\nCourse: {course_name} ({course_id}) - No students enrolled. ({remaining_seats_str})")
        
        if not found_enrollments and not assigned_courses.empty:
            print("No students enrolled in any of your assigned courses yet.")

# --- Student Class ---
class Student:
    def __init__(self, student_id):
        self.student_id = student_id
        students_df = load_data(STUDENTS_FILE, ['StudentID', 'StudentName', 'Password']) 
        self.student_name = students_df[students_df['StudentID'] == student_id]['StudentName'].iloc[0] if not students_df[students_df['StudentID'] == student_id].empty else "Unknown"

    def enroll_course(self):
        """Student enrolls into a course, updating capacity."""
        courses_df = load_data(COURSES_FILE, ['CourseID', 'CourseName', 'FacultyID', 'Capacity'])
        enrollments_df = load_data(ENROLLMENTS_FILE, ['StudentID', 'CourseID'])

        if courses_df.empty:
            print("No courses available for enrollment yet.")
            return

        print("\n--- Available Courses (with Remaining Seats) ---")
        display_courses_df = courses_df.copy()
        display_courses_df['Enrolled'] = display_courses_df['CourseID'].apply(lambda cid: enrollments_df[enrollments_df['CourseID'] == cid].shape[0])
        display_courses_df['Remaining Seats'] = display_courses_df.apply(lambda row: row['Capacity'] - row['Enrolled'] if row['Capacity'] > 0 else 'Unlimited', axis=1)
        print(display_courses_df[['CourseID', 'CourseName', 'Capacity', 'Remaining Seats']].to_string(index=False))

        course_id_to_enroll = input("Enter the Course ID you want to enroll in: ").strip().upper()

        if course_id_to_enroll not in courses_df['CourseID'].values:
            print("Invalid Course ID. Please choose from the available courses.")
            return

        # Check if student is already enrolled
        if not enrollments_df[(enrollments_df['StudentID'] == self.student_id) & 
                              (enrollments_df['CourseID'] == course_id_to_enroll)].empty:
            print(f"You are already enrolled in {course_id_to_enroll}.")
            return

        # Capacity check
        course_idx = courses_df[courses_df['CourseID'] == course_id_to_enroll].index[0]
        course_capacity = courses_df.loc[course_idx, 'Capacity']
        current_enrollment_count = enrollments_df[enrollments_df['CourseID'] == course_id_to_enroll].shape[0]

        if course_capacity > 0 and current_enrollment_count >= course_capacity:
            print(f"Sorry, {course_id_to_enroll} has reached its maximum capacity of {course_capacity}. No seats remaining.")
            return

        new_enrollment = pd.DataFrame([{'StudentID': self.student_id, 'CourseID': course_id_to_enroll}])
        enrollments_df = pd.concat([enrollments_df, new_enrollment], ignore_index=True)
        save_data(enrollments_df, ENROLLMENTS_FILE)
        
        # Update capacity - Decrement available slots
        # if course_capacity > 0: # Only decrement if capacity is limited (>0)
        #     courses_df.loc[course_idx, 'Capacity'] -= 1
        #     save_data(courses_df, COURSES_FILE)
        print(f"Successfully enrolled '{self.student_name}' ({self.student_id}) in '{courses_df.loc[course_idx, 'CourseName']}'. Available capacity updated.")

    def view_my_courses(self):
        """Student views their enrolled courses."""
        enrollments_df = load_data(ENROLLMENTS_FILE, ['StudentID', 'CourseID'])
        courses_df = load_data(COURSES_FILE, ['CourseID', 'CourseName', 'FacultyID', 'Capacity'])
        faculty_df = load_data(FACULTY_FILE, ['FacultyID', 'FacultyName', 'Password']) 

        my_enrollments = enrollments_df[enrollments_df['StudentID'] == self.student_id]

        if not my_enrollments.empty:
            print(f"\n--- Courses Enrolled by {self.student_name} ({self.student_id}) ---")
            merged_df = pd.merge(my_enrollments, courses_df, on='CourseID', how='left')
            merged_df = pd.merge(merged_df, faculty_df[['FacultyID', 'FacultyName']], on='FacultyID', how='left')
            
            # Calculate remaining seats for each of the student's enrolled courses
            enrollment_counts = enrollments_df.groupby('CourseID').size().reset_index(name='EnrolledCount')
            merged_df = pd.merge(merged_df, enrollment_counts, on='CourseID', how='left')
            merged_df['EnrolledCount'] = merged_df['EnrolledCount'].fillna(0).astype(int)

            merged_df['Remaining Seats'] = merged_df.apply(
                lambda row: row['Capacity'] - row['EnrolledCount'] if row['Capacity'] > 0 else 'Unlimited', axis=1
            )

            print(merged_df[['CourseID', 'CourseName', 'FacultyName', 'Capacity', 'Remaining Seats']].to_string(index=False))
        else:
            print(f"No courses enrolled by {self.student_name} ({self.student_id}) yet.")

# --- Main Program Loop ---

def main_menu():
    """Main menu for selecting user role and handling login."""
    print("--- Welcome to the Course Registration System ---")
    while True:
        print("\n--- Select User Role ---")
        print("1. Admin")
        print("2. Faculty")
        print("3. Student")
        print("4. Exit")
        
        user_role_choice = input("Enter your choice: ")

        if user_role_choice == '1':
            password = input("Enter Admin Password: ").strip()
            if authenticate_admin_misc("ADMIN", password): # Authenticate 'ADMIN' from passwords.csv
                admin_obj = Admin()
                while True:
                    print("\n--- Admin Menu ---")
                    print("1. Add New Faculty")
                    print("2. Add New Student")
                    print("3. Create New Course")
                    print("4. Modify Existing Course")
                    print("5. Manage Student Enrollments")
                    print("6. View All Faculty")
                    print("7. View All Students")
                    print("8. View All Courses") # This is where "Remaining Seats" is displayed
                    print("9. Logout")
                    admin_choice = input("Enter your choice: ")

                    if admin_choice == '1':
                        admin_obj.add_new_faculty()
                    elif admin_choice == '2':
                        admin_obj.add_new_student()
                    elif admin_choice == '3':
                        admin_obj.create_course()
                    elif admin_choice == '4':
                        admin_obj.modify_course()
                    elif admin_choice == '5':
                        admin_obj.manage_enrollments()
                    elif admin_choice == '6':
                        admin_obj.view_all_faculty()
                    elif admin_choice == '7':
                        admin_obj.view_all_students()
                    elif admin_choice == '8':
                        admin_obj.view_all_courses()
                    elif admin_choice == '9':
                        break
                    else:
                        print("Invalid choice. Please try again.")
            else:
                print("Admin login failed. Access denied.")

        elif user_role_choice == '2':
            faculty_id = input("Enter your Faculty ID: ").strip().upper()
            password = input("Enter Faculty Password: ").strip()
            if authenticate_faculty_student(faculty_id, password, 'faculty'):
                faculty_df = load_data(FACULTY_FILE, ['FacultyID', 'FacultyName', 'Password'])
                if faculty_id not in faculty_df['FacultyID'].values: 
                    print("Error: Faculty ID not found after successful password verification. Data inconsistency.")
                    continue
                faculty_obj = Faculty(faculty_id)
                while True:
                    print(f"\n--- Faculty Menu ({faculty_obj.faculty_name} - {faculty_obj.faculty_id}) ---")
                    print("1. Check Assigned Courses") # Displays Remaining Seats
                    print("2. Check Enrolled Students in My Courses") # Displays Remaining Seats for each course
                    print("3. Logout")
                    faculty_choice = input("Enter your choice: ")

                    if faculty_choice == '1':
                        faculty_obj.check_assigned_courses()
                    elif faculty_choice == '2':
                        faculty_obj.check_enrolled_students()
                    elif faculty_choice == '3':
                        break
                    else:
                        print("Invalid choice. Please try again.")
            else:
                print("Faculty login failed. Access denied.")

        elif user_role_choice == '3':
            student_id = input("Enter your Student ID: ").strip().upper()
            password = input("Enter Student Password: ").strip()
            if authenticate_faculty_student(student_id, password, 'student'):
                students_df = load_data(STUDENTS_FILE, ['StudentID', 'StudentName', 'Password'])
                if student_id not in students_df['StudentID'].values: 
                    print("Error: Student ID not found after successful password verification. Data inconsistency.")
                    continue
                student_obj = Student(student_id)
                while True:
                    print(f"\n--- Student Menu ({student_obj.student_name} - {student_obj.student_id}) ---")
                    print("1. Enroll in a Course") # Displays Remaining Seats
                    print("2. View My Enrolled Courses") # Displays Remaining Seats
                    print("3. Logout")
                    student_choice = input("Enter your choice: ")

                    if student_choice == '1':
                        student_obj.enroll_course()
                    elif student_choice == '2':
                        student_obj.view_my_courses()
                    elif student_choice == '3':
                        break
                    else:
                        print("Invalid choice. Please try again.")
            else:
                print("Student login failed. Access denied.")

        elif user_role_choice == '4':
            print("Exiting system. Goodbye! 👋")
            break
        else:
            print("Invalid choice. Please enter 1, 2, 3, or 4.")

if __name__ == "__main__":
    main_menu()
