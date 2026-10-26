import java.util.Scanner;

public class Basics {
    public static void main(String[] args) {
        // Convert Celsius to Fahrenheit
        Scanner in = new Scanner(System.in);
        System.out.println("Celsius?");
        double celsius = in.nextDouble();
        int rounded = 0;
        boolean hot = celsius > 30;
        String name = "Temperature";
        double fahrenheit = celsius * 9 / 5 + 32;
        rounded = (int) fahrenheit;
        System.out.println(name + ": " + rounded + " F, hot? " + hot);
    }
}
