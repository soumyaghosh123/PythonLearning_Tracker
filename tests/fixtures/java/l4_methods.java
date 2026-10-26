public class Methods {
    static void greet() {
        System.out.println("Welcome to the calculator");
    }

    static int add(int a, int b) {
        return a + b;
    }

    static double add(double a, double b) {
        return a + b;
    }

    static int factorial(int n) {
        if (n <= 1) {
            return 1;
        }
        return n * factorial(n - 1);
    }

    public static void main(String[] args) {
        greet();
        System.out.println(add(2, 3));
        System.out.println(add(2.5, 3.5));
        System.out.println(factorial(5));
    }
}
