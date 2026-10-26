import java.io.BufferedReader;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;

class NoteTooLongException extends Exception {
    NoteTooLongException(String message) {
        super(message);
    }
}

public class Notes {
    static void save(String note, String path) throws IOException, NoteTooLongException {
        if (note.length() > 200) {
            throw new NoteTooLongException("Note is too long");
        }
        try (FileWriter out = new FileWriter(path, true)) {
            out.write(note + "\n");
        }
    }

    static void show(String path) {
        try (BufferedReader in = new BufferedReader(new FileReader(path))) {
            String line;
            while ((line = in.readLine()) != null) {
                System.out.println(line);
            }
        } catch (IOException e) {
            System.out.println("Could not read: " + e.getMessage());
        } finally {
            System.out.println("Done reading");
        }
    }

    public static void main(String[] args) {
        try {
            save("Buy milk", "notes.txt");
            int x = 10 / (args.length);
        } catch (IOException | NoteTooLongException e) {
            System.out.println(e.getMessage());
        } catch (ArithmeticException e) {
            System.out.println("Divide by zero");
        }
        show("notes.txt");
    }
}
