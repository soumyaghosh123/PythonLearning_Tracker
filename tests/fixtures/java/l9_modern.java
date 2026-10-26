package app;

import java.util.List;
import java.util.stream.Collectors;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;

enum Grade { A, B, C }

record Student(String name, int score) {}

public class GradeManager {
    static Grade grade(int score) {
        return score >= 90 ? Grade.A : score >= 75 ? Grade.B : Grade.C;
    }

    public static void main(String[] args) {
        List<Student> students = List.of(new Student("Asha", 92), new Student("Ben", 70));
        List<String> top = students.stream()
                .filter(s -> s.score() >= 75)
                .map(Student::name)
                .collect(Collectors.toList());
        System.out.println(top);
        students.forEach(s -> System.out.println(s.name() + " " + grade(s.score())));
    }
}

class GradeManagerTest {
    @Test
    void ninetyIsAnA() {
        assertEquals(Grade.A, GradeManager.grade(90));
    }
}
