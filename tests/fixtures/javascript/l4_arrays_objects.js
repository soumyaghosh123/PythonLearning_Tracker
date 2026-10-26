// Level 4: arrays and objects
const nums = [1, 2, 3, 4];
nums.push(5);
const doubled = nums.map((n) => n * 2);
const evens = nums.filter((n) => n % 2 === 0);
const total = nums.reduce((sum, n) => sum + n, 0);

const person = { name: "Asha", age: 12 };
const { name, age } = person;
const copy = { ...person, age: 13 };
const more = [...nums, 6, 7];
console.log(doubled, evens, total, name, age, copy, more);
