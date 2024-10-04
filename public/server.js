const express = require('express');
const bodyParser = require('body-parser');
const { Pool } = require('pg');
const path = require('path');
const dotenv = require('dotenv');

dotenv.config();

const app = express();

// Change port to 80 for public access without specifying a port
const port = process.env.PORT || 80;

const pool = new Pool({
    connectionString: process.env.DATABASE_URL,
    ssl: {
        rejectUnauthorized: false
    }
});

app.use(bodyParser.json());
app.use(express.static(path.join(__dirname, 'public')));

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'gaze.html'));
});

app.post('/save-gaze-data', async (req, res) => {
    const data = req.body;
    const query = 'INSERT INTO gaze_data (eye_x, eye_y, timestamp) VALUES ($1, $2, $3)';
    try {
        for (const entry of data) {
            await pool.query(query, [entry.eyeX, entry.eyeY, entry.timestamp]);
        }
        console.log('Gaze data saved!');
        res.status(200).send('Data received');
    } catch (err) {
        console.error('Error saving gaze data:', err);
        res.status(500).send('Error saving data');
    }
});

app.listen(port, () => {
    console.log(`Server running on port ${port}`);
});
