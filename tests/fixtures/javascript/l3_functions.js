// Level 3: functions
function greet(name, greeting = "Hello") {
  return `${greeting}, ${name}`;
}

const square = (x) => x * x;

function makeCounter() {
  let count = 0;
  return function () {
    count += 1;
    return count;
  };
}

const next = makeCounter();
console.log(greet("Asha"), square(4), next(), next());
