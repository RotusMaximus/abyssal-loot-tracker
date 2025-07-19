# Abyssal Loot Tracker

## ⚠️ Disclaimer

> [!WARNING]
> This software was developed with the aid of an AI assistant. While the code has been reviewed, modified and tested, it is provided "as-is", without any express or implied warranties.
> Use it at your own risk. No guarantees are made regarding its accuracy, reliability, or suitability for any particular purpose.
>
> This project is not affiliated with, endorsed, or sponsored by CCP Games.
> EVE Online and all related logos, names, and design elements are the intellectual property of CCP hf.
> All trademarked content remains the property of its respective owners.

## ℹ️ About this repository

This repository contains a Python-based desktop utility designed for **EVE Online** players who run **Abyssal Sites**. It actively monitors the system clipboard for loot data copied in-game, takes in metadata, stores that information locally, and calculates estimated profit per run based on current item values (utilizing the [EVE Tycoon](https://evetycoon.com/) API). It aims to provide similar functionality to and is inspired by the run recording feature of the [Abyss Tracker](https://abysstracker.com/) and [Abyssal Telemetry](https://abyssal.space/) while saving data completely offline and providing some convenience features that are not easily achievable by a web-based application.

### Current Project State

This project is very early in development. Breaking changes are likely and expected.

### Why Was This Made?

Other solutions to track Abyssal Site Runs exist, even offline ones, however these tend to be bare bones or come with other caveats (like being included in a big toolbox of EVE tools). I wanted a standalone tool that would function even without relying on someone elses server to store my runs, while being fast and easy to use.

Right now it's a fairly simple tool, however I'd like to leverage the additional options gained by being a locally running tool in the future (like reading combat logs).

## 📋 Table of Contents

- [Abyssal Loot Tracker](#abyssal-loot-tracker)
  - [⚠️ Disclaimer](#️-disclaimer)
  - [ℹ️ About this repository](#ℹ️-about-this-repository)
    - [Current Project State](#current-project-state)
    - [Why Was This Made?](#why-was-this-made)
  - [📋 Table of Contents](#-table-of-contents)
  - [✨ Features](#-features)
  - [🧰 Prerequisites](#-prerequisites)
  - [🚀 Usage](#-usage)
    - [Installation \& Basic Usage](#installation--basic-usage)

## ✨ Features

- Clipboard monitoring for Abyssal Loot during site runs
- Automatic parsing and local saving of each run
- Price checks and profit estimation per run
- Easy-to-browse run history

## 🧰 Prerequisites

> [!IMPORTANT]
> Python needs to be available in PATH (be sure to tick the box during installation)

- Python **3.12** or newer — Download from [python.org](https://www.python.org/downloads/).
- Git — Download from [git-scm.com](https://git-scm.com/downloads) _(optional, see below for alternatives)_

## 🚀 Usage

### Installation & Basic Usage

1. **Get the code**
   Option 1: Clone the repository using Git

   ```bash
   git clone https://github.com/RotusMaximus/abyssal-loot-tracker.git
   ```

   Option 2: Download as a `.zip`

   - Click the green **Code** button on the [repository page](https://github.com/RotusMaximus/abyssal-loot-tracker.git)
   - Select **Download ZIP**
   - Extract the archive to a folder of your choice

2. **Run the tool**

   - Locate and double-click the `run.bat` file inside the folder
   - The script will perform an initial setup the first time it's run

3. **Track loot**

   - After setup, simply use `run.bat` anytime you want to launch the tool
   - Then simply follow the instructions given on screen to save your runs!
