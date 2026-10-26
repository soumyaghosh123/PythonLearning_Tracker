public class ArraysStrings {
    public static void main(String[] args) {
        int[] scores = {90, 85, 77, 62, 100};
        int total = 0;
        for (int s : scores) {
            total += s;
        }
        System.out.println("Third score: " + scores[2] + ", total " + total);

        int[][] grid = new int[3][3];
        for (int r = 0; r < grid.length; r++) {
            for (int c = 0; c < grid[r].length; c++) {
                grid[r][c] = r * c;
            }
        }

        String sentence = "the quick brown fox";
        System.out.println(sentence.length() + " " + sentence.toUpperCase() + " " + sentence.charAt(4));
        StringBuilder sb = new StringBuilder();
        for (String word : sentence.split(" ")) {
            sb.append(word.charAt(0));
        }
        System.out.println(sb.toString());
    }
}
