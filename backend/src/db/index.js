const { Pool } = require('pg');

const pool = new Pool({
    // connection config will be automatically read from environment variables
    // PGUSER, PGHOST, PGPASSWORD, PGDATABASE, PGPORT
});

module.exports = {
    query: (text, params) => pool.query(text, params),
}; 