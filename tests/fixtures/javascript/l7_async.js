// Level 7: asynchronous JS
setTimeout(() => console.log("later"), 100);

const wait = (ms) =>
  new Promise((resolve) => setTimeout(resolve, ms));

wait(50).then(() => console.log("done"));

async function loadUser(id) {
  const res = await fetch(`https://example.com/users/${id}`);
  return res.json();
}

loadUser(1).catch(console.error);
