interface Shape {
    double area();
}

abstract class Animal {
    protected String name;

    Animal(String name) {
        this.name = name;
    }

    abstract String speak();
}

class Dog extends Animal {
    Dog(String name) {
        super(name);
    }

    @Override
    String speak() {
        return name + " says Woof";
    }
}

class Circle implements Shape {
    private final double r;

    Circle(double r) {
        this.r = r;
    }

    @Override
    public double area() {
        return Math.PI * r * r;
    }
}

public class Inheritance {
    public static void main(String[] args) {
        Animal pet = new Dog("Rex");
        System.out.println(pet.speak());
        Shape s = new Circle(2);
        System.out.println(s.area());
    }
}
