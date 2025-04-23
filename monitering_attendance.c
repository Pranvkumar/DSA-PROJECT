#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define TABLE_SIZE 10
#define MAX_NAME_LEN 50
#define MAX_LINE_LEN 100
#define MAX_SUBJECTS 10
#define MAX_DAYS 31
#define RESET "\033[0m"
#define RED "\033[31m"
#define GREEN "\033[32m"
#define YELLOW "\033[33m"
#define BLUE "\033[34m"
#define MAGENTA "\033[35m"
#define CYAN "\033[36m"
#define BOLD "\033[1m"

typedef struct AttendanceRecord
{
    int days[MAX_DAYS];
} AttendanceRecord;

typedef struct Student
{
    int id;
    char name[MAX_NAME_LEN];
    AttendanceRecord subjects[MAX_SUBJECTS];
    struct Student *next;
} Student;

Student *hashTable[TABLE_SIZE] = {NULL};
char subjectList[MAX_SUBJECTS][MAX_NAME_LEN];
int subjectCount = 0;

int hashFunction(int id)
{
    return id % TABLE_SIZE;
}

Student *createStudent(int id, const char *name)
{
    Student *newStudent = (Student *) malloc(sizeof(Student));
    if (!newStudent)
    {
        printf("Error: Memory allocation failed.\n");
        exit(EXIT_FAILURE);
    }
    newStudent->id = id;
    strncpy(newStudent->name, name, MAX_NAME_LEN - 1);
    newStudent->name[MAX_NAME_LEN - 1] = '\0';
    for (int i = 0; i < MAX_SUBJECTS; i++)
    {
        memset(newStudent->subjects[i].days, 0, sizeof(newStudent->subjects[i].days));
    }
    newStudent->next = NULL;
    return newStudent;
}

void insertStudent(int id, const char *name)
{
    int index = hashFunction(id);
    Student *newStudent = createStudent(id, name);
    newStudent->next = hashTable[index];
    hashTable[index] = newStudent;
}

Student *searchStudentById(int id)
{
    int lastFourDigits = id % 10000;
    for (int i = 0; i < TABLE_SIZE; i++)
    {
        Student *current = hashTable[i];
        while (current != NULL)
        {
            if (current->id % 10000 == lastFourDigits)
            {
                return current;
            }
            current = current->next;
        }
    }
    return NULL;
}

void deleteStudentById(int id)
{
    int index = hashFunction(id);
    Student *current = hashTable[index];
    Student *prev = NULL;

    while (current != NULL)
    {
        if (current->id == id)
        {
            if (prev == NULL)
            {
                hashTable[index] = current->next;
            }
            else
            {
                prev->next = current->next;
            }
            free(current);
            printf("Student with ID %d deleted successfully.\n", id);
            return;
        }
        prev = current;
        current = current->next;
    }

    printf("Student with ID %d not found.\n", id);
}

int getSubjectIndex(const char *subject)
{
    for (int i = 0; i < subjectCount; i++)
    {
        if (strcmp(subjectList[i], subject) == 0)
        {
            return i;
        }
    }
    if (subjectCount < MAX_SUBJECTS)
    {
        strncpy(subjectList[subjectCount], subject, MAX_NAME_LEN - 1);
        subjectList[subjectCount][MAX_NAME_LEN - 1] = '\0';
        return subjectCount++;
    }
    printf("Error: Maximum number of subjects reached.\n");
    return -1;
}

void markAttendance()
{
    char subject[MAX_NAME_LEN];
    int day;

    printf("Enter the subject name: ");
    scanf("%s", subject);
    int subjectIndex = getSubjectIndex(subject);
    if (subjectIndex == -1)
    {
        return;
    }

    printf("Enter the day of the month (1-31): ");
    if (scanf("%d", &day) != 1 || day < 1 || day > MAX_DAYS)
    {
        printf("Error: Invalid day.\n");
        return;
    }

    int id = 0;
    printf(
        "Enter last 4 digits of student ID to mark attendance for %s on day %d (or -1 to stop): ",
        subject, day);
    while (scanf("%d", &id) && id != -1)
    {
        Student *student = NULL;
        for (int i = 0; i < TABLE_SIZE; i++)
        {
            Student *current = hashTable[i];
            while (current != NULL)
            {
                if (current->id % 10000 == id)
                {
                    student = current;
                    break;
                }
                current = current->next;
            }
            if (student)
            {
                break;
            }
        }

        if (student)
        {
            student->subjects[subjectIndex].days[day - 1] = 1;
            printf("Marked %s (ID: %d) as present for %s on day %d.\n", student->name, student->id,
                   subject, day);
        }
        else
        {
            printf("Student with last 4 digits of ID %d not found.\n", id);
        }
        printf("Enter next last 4 digits of student ID to mark attendance for %s on day %d (or -1 "
               "to stop): ",
               subject, day);
    }
}

void loadStudentsFromFile(const char *filename)
{
    FILE *file = fopen(filename, "r");
    if (!file)
    {
        printf("Error: Could not open file %s\n", filename);
        return;
    }

    char line[MAX_LINE_LEN];
    while (fgets(line, sizeof(line), file))
    {
        int id;
        char name[MAX_NAME_LEN];
        if (sscanf(line, "%d,%49[^\n]", &id, name) == 2)
        {
            insertStudent(id, name);
        }
        else
        {
            printf("Warning: Skipping invalid line: %s", line);
        }
    }

    fclose(file);
    printf("Students loaded successfully from %s\n", filename);
}

void generateReport(const char *filename, const char *subject)
{
    FILE *file = fopen(filename, "w");
    if (!file)
    {
        printf("Error: Could not open file %s for writing\n", filename);
        return;
    }

    int subjectIndex = getSubjectIndex(subject);
    if (subjectIndex == -1)
    {
        fclose(file);
        return;
    }

    int minDay = MAX_DAYS + 1, maxDay = 0;
    for (int i = 0; i < TABLE_SIZE; i++)
    {
        Student *current = hashTable[i];
        while (current != NULL)
        {
            for (int day = 0; day < MAX_DAYS; day++)
            {
                if (current->subjects[subjectIndex].days[day])
                {
                    if (day + 1 < minDay)
                        minDay = day + 1;
                    if (day + 1 > maxDay)
                        maxDay = day + 1;
                }
            }
            current = current->next;
        }
    }

    if (minDay > maxDay)
    {
        printf("No attendance data available for subject %s.\n", subject);
        fclose(file);
        return;
    }

    fprintf(file, "%s Attendance Report\n", subject);
    fprintf(file, "%-10s %-30s", "ID", "Name");
    for (int day = minDay; day <= maxDay; day++)
    {
        fprintf(file, " Day%-2d", day);
    }
    fprintf(file, "\n");
    fprintf(
        file,
        "--------------------------------------------------------------------------------------\n");

    for (int i = 0; i < TABLE_SIZE; i++)
    {
        Student *current = hashTable[i];
        while (current != NULL)
        {
            fprintf(file, "%-10d %-30s", current->id, current->name);
            for (int day = minDay; day <= maxDay; day++)
            {
                fprintf(file, " %-5s", current->subjects[subjectIndex].days[day - 1] ? "P" : "A");
            }
            fprintf(file, "\n");
            current = current->next;
        }
    }

    fclose(file);
    printf("Attendance report for %s generated successfully in %s\n", subject, filename);
}

void viewAttendance()
{
    int id;
    printf("Enter student ID to view attendance: ");
    if (scanf("%d", &id) != 1)
    {
        printf("Error: Invalid input for ID.\n");
        return;
    }

    Student *student = searchStudentById(id);
    if (!student)
    {
        printf("Student with ID %d not found.\n", id);
        return;
    }

    printf("\nAttendance for %s (ID: %d):\n", student->name, student->id);
    printf(
        "======================================================================================\n");

    for (int part = 0; part < 3; part++)
    {
        int startDay = part * 10 + 1;
        int endDay = (part == 2) ? MAX_DAYS : startDay + 9;

        printf("| %-20s", "Subject");
        for (int day = startDay; day <= endDay; day++)
        {
            printf("| Day%-2d ", day);
        }
        printf("|\n");
        printf("==================================================================================="
               "===\n");

        for (int i = 0; i < subjectCount; i++)
        {
            printf("| %-20s", subjectList[i]);
            for (int day = startDay - 1; day < endDay; day++)
            {
                printf("| %-5s ", student->subjects[i].days[day] ? "P" : "A");
            }
            printf("|\n");
        }
        printf("==================================================================================="
               "===\n");
    }
}

void freeHashTable()
{
    for (int i = 0; i < TABLE_SIZE; i++)
    {
        Student *current = hashTable[i];
        while (current != NULL)
        {
            Student *temp = current;
            current = current->next;
            free(temp);
        }
        hashTable[i] = NULL;
    }
}

void printColoredMessage(const char *message, const char *color)
{
    printf("%s%s%s\n", color, message, RESET);
}

int main()
{
    int choice;
    char inputFile[100], reportFile[100], subject[MAX_NAME_LEN];

    while (1)
    {
        printf("\n" BOLD CYAN "Attendance Management System" RESET "\n");
        printf(BLUE "1. Load Students from File\n" RESET);
        printf(BLUE "2. Generate Attendance Report\n" RESET);
        printf(BLUE "3. Search Student by ID\n" RESET);
        printf(BLUE "4. Delete Student by ID\n" RESET);
        printf(BLUE "5. Insert New Student\n" RESET);
        printf(BLUE "6. Mark Attendance\n" RESET);
        printf(BLUE "7. View Attendance\n" RESET);
        printf(BLUE "8. Exit\n" RESET);
        printf(YELLOW "Enter your choice: " RESET);
        if (scanf("%d", &choice) != 1)
        {
            printColoredMessage("Error: Invalid input. Please enter a number.", RED);
            while (getchar() != '\n')
                ;
            continue;
        }

        switch (choice)
        {
            case 1:
                printf(YELLOW "Enter input file name: " RESET);
                scanf("%s", inputFile);
                loadStudentsFromFile(inputFile);
                break;
            case 2:
                printf(YELLOW "Enter the subject name: " RESET);
                scanf("%s", subject);
                printf(YELLOW "Enter report file name: " RESET);
                scanf("%s", reportFile);
                generateReport(reportFile, subject);
                break;
            case 3:
            {
                int id;
                printf(YELLOW "Enter student ID to search: " RESET);
                if (scanf("%d", &id) != 1)
                {
                    printColoredMessage("Error: Invalid input for ID.", RED);
                    break;
                }
                Student *student = searchStudentById(id);
                if (student)
                {
                    printColoredMessage("Student found:", GREEN);
                    printf(GREEN "ID: %d\n" RESET, student->id);
                    printf(GREEN "Name: %s\n" RESET, student->name);
                }
                else
                {
                    printColoredMessage("Student with ID not found.", RED);
                }
                break;
            }
            case 4:
            {
                int id;
                printf(YELLOW "Enter student ID to delete: " RESET);
                if (scanf("%d", &id) != 1)
                {
                    printColoredMessage("Error: Invalid input for ID.", RED);
                    break;
                }
                deleteStudentById(id);
                break;
            }
            case 5:
            {
                int id;
                char name[MAX_NAME_LEN];

                printf(YELLOW "Enter student ID: " RESET);
                if (scanf("%d", &id) != 1)
                {
                    printColoredMessage("Error: Invalid input for ID.", RED);
                    break;
                }
                printf(YELLOW "Enter student name: " RESET);
                getchar();
                if (!fgets(name, sizeof(name), stdin))
                {
                    printColoredMessage("Error: Invalid input for name.", RED);
                    break;
                }
                name[strcspn(name, "\n")] = '\0';

                if (searchStudentById(id))
                {
                    printColoredMessage("Error: Student with ID already exists.", RED);
                    break;
                }

                insertStudent(id, name);
                printColoredMessage("Student added successfully.", GREEN);
                break;
            }
            case 6:
                markAttendance();
                break;
            case 7:
                viewAttendance();
                break;
            case 8:
                freeHashTable();
                printColoredMessage("Exiting...", GREEN);
                return 0;
            default:
                printColoredMessage("Invalid choice. Try again.", RED);
        }
    }
}
