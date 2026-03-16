const { routes } = require("./routes");
const { config } = require("./config");

function createServer() {
  return { routes, config };
}

module.exports = { createServer };
