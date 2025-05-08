-- Creating the Greenhouse Gas Emissions Database Schema (SQLite Version)

-- 1. Creating the `Greenhouse_Gases` dimension table
CREATE TABLE IF NOT EXISTS Greenhouse_Gases (
    ghg_id INTEGER PRIMARY KEY,
    ghg_name TEXT NOT NULL,
    ghg_category TEXT
);

-- 2. Creating the `Sectors` dimension table (combined for Economic and IPCC Sectors)
CREATE TABLE IF NOT EXISTS Sectors (
    sector_id INTEGER PRIMARY KEY,
    sector TEXT NOT NULL,
    subsector TEXT,
    category TEXT,
    sub_category_1 TEXT,
    sub_category_2 TEXT,
    sub_category_3 TEXT,
    sub_category_4 TEXT,
    sub_category_5 TEXT,
    dataset_type TEXT NOT NULL
);

-- 3. Creating the `Fuels` dimension table
CREATE TABLE IF NOT EXISTS Fuels (
    fuel_id INTEGER PRIMARY KEY,
    fuel1 TEXT NOT NULL,
    fuel2 TEXT
);

-- 4. Creating the `Geography` dimension table
CREATE TABLE IF NOT EXISTS Geography (
    geo_id INTEGER PRIMARY KEY,
    geo_ref TEXT NOT NULL
);

-- 5. Creating the `Emissions` fact table
CREATE TABLE Emissions (
    emission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    ghg_id INTEGER,
    sector_id INTEGER,
    fuel_id INTEGER,
    geo_id INTEGER,
    emissions REAL NOT NULL,
    FOREIGN KEY (ghg_id) REFERENCES Greenhouse_Gases (ghg_id),
    FOREIGN KEY (sector_id) REFERENCES Sectors (sector_id),
    FOREIGN KEY (fuel_id) REFERENCES Fuels (fuel_id),
    FOREIGN KEY (geo_id) REFERENCES Geography (geo_id)
);

-- Importing Data into Tables (SQLite uses .import command)
-- Run the following commands in SQLite shell

-- 1. Importing Greenhouse Gases Data
.mode csv
.import --csv emissionsData/Greenhouse_Gases.csv Greenhouse_Gases

-- 2. Importing Sectors Data
.import --csv emissionsData/Sectors.csv Sectors

-- 3. Importing Fuels Data
.import --csv emissionsData/Fuels.csv Fuels

-- 4. Importing Geography Data
.import --csv emissionsData/Geography.csv Geography

-- 5. Importing Emissions Data
.import --csv emissionsData/Emissions.csv Emissions

DROP TABLE IF EXISTS Greenhouse_Gases;

CREATE TABLE Greenhouse_Gases (
    ghg_id INTEGER PRIMARY KEY,
    ghg_name TEXT NOT NULL,
    ghg_category TEXT
);