// Level 8: classes and modern JS
class Animal {
  static count = 0;
  constructor(name) {
    this.name = name;
    Animal.count++;
  }
  get label() {
    return `Animal ${this.name}`;
  }
  speak() {
    return "...";
  }
}

class Dog extends Animal {
  speak() {
    return super.speak() + "Woof";
  }
}

const seen = new Set(["a"]);
const owners = new Map();
owners.set("rex", { city: "Pune" });
const d = new Dog("Rex");
console.log(d.label, seen, owners.get("rex")?.city);
