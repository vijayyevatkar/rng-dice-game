"use strict";

setupNewGame();

var scores,
  scoreInThisRound,
  activePlayer,
  continueGame,
  prevScore,
  waiting,
  play,
  dice,
  finalScore;
var map = ["Player 1", "Player 2"];
waiting = "Waiting for my turn!";
play = "I will play now!";
finalScore = 50;

document.querySelector(".btn--new").addEventListener("click", setupNewGame);
document.querySelector(".btn--roll").addEventListener("click", buttonRoll);
document.querySelector(".btn--hold").addEventListener("click", buttonHold);

function setupNewGame() {
  continueGame = true;
  scores = [0, 0];
  scoreInThisRound = 0;
  activePlayer = 0;
  prevScore = 0;
  document.querySelector(".dice0").style.display = "none";
  document.querySelector(".dice1").style.display = "none";
  document.getElementById("current--0").textContent = 0;
  document.getElementById("current--1").textContent = 0;
  document.getElementById("score--0").textContent = 0;
  document.getElementById("score--1").textContent = 0;
  document.querySelector(".player--0").classList.remove("player--active");
  document.querySelector(".player--1").classList.remove("player--active");
  document.querySelector(".player--0").classList.remove("player--winner");
  document.querySelector(".player--1").classList.remove("player--winner");
  document.querySelector(".player--0").classList.add("player--active");
  document.querySelector(".player--1").classList.remove("player--subtext--win");
  document.querySelector(".player--0").classList.remove("player--subtext--win");
  document.getElementById("sub-1").textContent = "Waiting for my turn!";
  document.getElementById("sub-0").textContent = "Roll Dice!";
}

function buttonRoll() {
  if (!continueGame) return;
  let otherPlayer = activePlayer - 1;
  if (otherPlayer < 0) otherPlayer = 1;
  var diceNum = Math.floor(Math.random() * 6) + 1;
  var diceDOM = document.querySelector(".dice" + activePlayer);
  var diceDOMHide = document.querySelector(".dice" + otherPlayer);
  diceDOM.style.display = "block";
  diceDOMHide.style.display = "none";
  diceDOM.src = "dice-" + diceNum + ".png";
  if (diceNum === 1) {
    document.getElementById("sub-" + activePlayer).textContent =
      "Oh No! I rolled a 1 😐";
    changeActivePlayer(0);
  } else {
    scoreInThisRound += diceNum;
    let currentTotal = scoreInThisRound + prevScore;
    document.getElementById(
      "current--" + activePlayer
    ).textContent = scoreInThisRound;
    if (currentTotal >= finalScore) {
      endGame();
    } else {
      document.getElementById("sub-" + activePlayer).textContent =
        "Yay! I rolled a " + diceNum;
      document.getElementById("sub-" + otherPlayer).textContent =
        "Waiting for my turn!";
    }
  }
}

function endGame() {
  document
    .querySelector(".player--" + activePlayer)
    .classList.remove("player--active");
  document
    .querySelector(".player--" + activePlayer)
    .classList.add("player--winner");
  continueGame = false;
  document.getElementById("score--" + activePlayer).textContent =
    scoreInThisRound + prevScore;
  document
    .getElementById("sub-" + activePlayer)
    .classList.add("player--subtext--win");
  document.getElementById("sub-" + activePlayer).textContent =
    "Yay! I won!! 🎉";
  activePlayer ? (activePlayer = 0) : (activePlayer = 1);
  document.getElementById("sub-" + activePlayer).textContent =
    "Nooo! I lost 🙁";
}

function changeActivePlayer(keepScore) {
  if (!continueGame) return;
  document
    .querySelector(".player--" + activePlayer)
    .classList.remove("player--active");
  prevScore = parseInt(
    document.getElementById("score--" + activePlayer).textContent,
    10
  );
  let addedScore = prevScore;
  if (keepScore) addedScore = scoreInThisRound + prevScore;
  document.getElementById("score--" + activePlayer).textContent = addedScore;
  document.getElementById("current--" + activePlayer).textContent = 0;
  activePlayer ? (activePlayer = 0) : (activePlayer = 1);
  scoreInThisRound = 0;
  if (keepScore)
    document.getElementById("sub-" + activePlayer).textContent =
      "It's my turn now.";
  else {
    document.getElementById("sub-" + activePlayer).textContent =
      "Ha-ha 😂 it's my turn now.";
  }
  document
    .querySelector(".player--" + activePlayer)
    .classList.add("player--active");

  prevScore = parseInt(
    document.getElementById("score--" + activePlayer).textContent,
    10
  );
}

function buttonHold() {
  if (!continueGame) return;
  document.getElementById("sub-" + activePlayer).textContent =
    "I will hold for now.";
  changeActivePlayer(1);
}
