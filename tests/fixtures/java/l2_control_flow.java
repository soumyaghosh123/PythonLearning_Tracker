import java.util.Scanner;

public class ControlFlow {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in);
        int secret = 7;
        int tries = 0;
        int guess = -1;
        while (guess != secret && tries < 5) {
            System.out.println("Guess?");
            guess = in.nextInt();
            tries++;
            if (guess < secret) {
                System.out.println("Too low");
            } else if (guess > secret) {
                System.out.println("Too high");
            } else {
                System.out.println("Correct!");
            }
        }
        for (int i = 1; i <= 20; i++) {
            if (i % 2 == 0) {
                continue;
            }
            if (i > 15) {
                break;
            }
            System.out.println(i);
        }
        int day = 3;
        switch (day) {
            case 1:
                System.out.println("Monday");
                break;
            case 3:
                System.out.println("Wednesday");
                break;
            default:
                System.out.println("Another day");
        }
        int n = 3;
        do {
            n--;
        } while (n > 0);
    }
}
