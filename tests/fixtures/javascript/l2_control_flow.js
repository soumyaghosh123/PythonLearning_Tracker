// Level 2: control flow
const scores = [72, 45, 90];
for (let i = scores.length - 1; i >= 0; i--) {
  const s = scores[i];
  if (s >= 60) {
    console.log(s, "pass");
  } else if (s === 45) {
    console.log("so close");
  } else {
    console.log("fail");
  }
}

let n = 0;
while (n < 5) {
  n++;
  if (n === 2) continue;
  if (n === 4) break;
}

const day = 3;
switch (day) {
  case 1:
    console.log("Mon");
    break;
  default:
    console.log("Other");
}

const label = n !== 0 ? "started" : "idle";
console.log(label);
for (const s of scores) {
  console.log(s);
}
