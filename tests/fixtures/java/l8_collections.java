import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

class Box<T> {
    private T item;

    Box(T item) {
        this.item = item;
    }

    T get() {
        return item;
    }
}

public class Collections {
    public static void main(String[] args) {
        List<String> names = new ArrayList<>();
        names.add("Charlie");
        names.add("Al");
        names.add("Barbara");
        names.sort(Comparator.comparing(String::length));
        System.out.println(names + " size " + names.size());

        Map<String, Integer> ages = new HashMap<>();
        ages.put("Al", 30);
        ages.put("Barbara", 41);
        System.out.println(ages.get("Al"));

        Set<Integer> unique = new HashSet<>();
        unique.add(1);
        unique.add(1);
        System.out.println(unique.size());

        Box<String> box = new Box<>("gift");
        System.out.println(box.get());
    }
}
