public class Bank {
    public static void main(String[] args) {
        BankAccount acct = new BankAccount("Asha", 100.0);
        acct.deposit(50);
        if (!acct.withdraw(500)) {
            System.out.println("Insufficient funds");
        }
        System.out.println(acct.getOwner() + " has " + acct.getBalance());
        System.out.println(BankAccount.getCount() + " account(s)");
    }
}

class BankAccount {
    private static int count = 0;
    private String owner;
    private double balance;

    public BankAccount(String owner, double balance) {
        this.owner = owner;
        this.balance = balance;
        count++;
    }

    public void deposit(double amount) {
        if (amount > 0) {
            balance += amount;
        }
    }

    public boolean withdraw(double amount) {
        if (amount > balance) {
            return false;
        }
        balance -= amount;
        return true;
    }

    public String getOwner() {
        return owner;
    }

    public double getBalance() {
        return balance;
    }

    public static int getCount() {
        return count;
    }
}
