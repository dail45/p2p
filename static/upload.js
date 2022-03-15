function changeChunkSize(from1, from2) {
  chunkSize = from1.value * (2 ** (10 * strSizeFormatToInt(from2.value)))
}

function strSizeFormatToInt(sizeFormat) {
  switch (sizeFormat) {
    case "B":
      return 0
    case "KB":
      return 1
    case "MB":
      return 2
  }
}

function formatSize(size) {
  let newSize = size
  let typeSize = "B"
  let typeSizeInt = 0
  if (newSize >= 1024) {
    newSize /= 1024
    typeSize = "KB"
    typeSizeInt++
  }
  if (newSize >= 1024) {
    newSize /= 1024
    typeSize = "MB"
    typeSizeInt++
  }
  if (newSize >= 1024) {
    newSize /= 1024
    typeSize = "GB"
    typeSizeInt++
  }
  return Array.of([newSize, typeSize, typeSizeInt])
}

async function register() {
  regBtn.disabled = true
  startBtn.disabled = false
  response = await fetch("/reg")
  rnum = await response.text()
  document.getElementById("rnumLabel").innerText = "rnum: " + rnum
  setTimeout(() => {regBtn.disabled = false}, 1000)
  initBtn.disabled = false
  regFlag = true
  initFlag = false
  initFlag = false
  doneFlag = false
}

async function init() {
  if (fileFlag === false) {
    return
  }
  regBtn.disabled = true
  initBtn.disabled = true
  startBtn.disabled = true
  let data = {
    "chunksize": chunkSize,
    "threads": threads,
    "RAM": 64 * (2 ** 20),
    "filename": file.name,
    "totallength": file.size
  }
  let sendJson = JSON.stringify(data)
  response = await fetch(`/start/${rnum}`, {
    method: "POST",
    body: sendJson
  })
  let log = await response.json()
  console.log(log)
  setTimeout(() => {regBtn.disabled = false;initBtn.disabled = false}, 1000)
  startBtn.disabled = false
}

async function start() {
  regBtn.disabled = true
  initBtn.disabled = true
  startBtn.disabled = true
  startThread()
}

let chunksCounter = 0
async function startThread() {
  while (doneFlag === false) {
    if (threadsOn >= threads) {
      setTimeout(async () => {
        await startThread()
      }, 50)
      return
    }
    /*if (chunkSize * (chunksCounter - 1) >= file.size) {
      doneFlag = true
      console.log(`upload done ${uploaded} ${uploadedBytes}`)
      break
    }*/
    if (file.size - chunkSize * chunksCounter <= 0) {
      doneFlag = true
      break
    }
    threadsOn++
    let chunk = await readChunk(chunkSize * chunksCounter, chunkSize * (chunksCounter + 1))
    sendChunk(chunk, chunksCounter)
    chunksCounter++
  }
}

async function sendChunk(chunk, index) {
  if (chunk.size === 0) {
    return
  }
  while (true) {
    let r = await fetch(`/uploadawait/${rnum}`)
    let rjs = await r.json()
    console.log(JSON.stringify(rjs))
    if (rjs["status"] === "dead") {
      doneFlag = true
      threadsOn--
      console.log(`upload done ${uploaded} ${uploadedBytes}`)
      break
    }
    if (rjs["status"] === "alive-timeout") {
      continue
    }
    if (rjs["status"] === "alive") {
      await fetch(`/uploadChunk/${rnum}?index=${index}`, {
        method: "POST",
        body: chunk
      })
      uploaded++
      uploadedBytes += chunk.length
      threadsOn--
      if (uploadedBytes === file.size) {
        doneFlag = true
        console.log(`upload done ${uploaded} ${uploadedBytes}`)
      }
      break
    }

  }
}

async function readChunk(start, end) {
  return new Promise((resolve, reject) => {
    let sl = file.slice(start, end)
    let FR = new FileReader()
    FR.onload = () => {
      resolve(FR.result)
    }
    FR.error = reject
    FR.readAsArrayBuffer(sl)
  })
}


let fileFlag = false
let regFlag = false
let initFlag = false
let doneFlag = false
let rnum = 0
let file = null
let chunkSize = 4 * (2 ** 20)
let threads = 16
let threadsOn = 0
let uploaded = 0
let uploadedBytes = 0
let speed = 0
let fileBtn = document.getElementById("uploadbtn")
let regBtn = document.getElementById("regBtn")
let chunkSizeInput = document.getElementById("numberChunkSizeInput")
let chunkSizeTypeInput = document.getElementById("typeChunkSizeSelect")
let threadsInput = document.getElementById("threadCountInput")
let initBtn = document.getElementById("initBtn")
let progressBar = document.getElementById("progressBar")
let progressBarValue = document.getElementById("progressBarValue")
let chunksLabel = document.getElementById("ChunksLabel")
let sizeLabel = document.getElementById("SizeLabel")
let speedLabel = document.getElementById("SpeedLabel")
let startBtn = document.getElementById("startBtn")

document.addEventListener("readystatechange", () => {
  if (document.readyState === "complete") {
     fileBtn = document.getElementById("uploadbtn")
     regBtn = document.getElementById("regBtn")
     chunkSizeInput = document.getElementById("numberChunkSizeInput")
     chunkSizeTypeInput = document.getElementById("typeChunkSizeSelect")
     threadsInput = document.getElementById("threadCountInput")
     initBtn = document.getElementById("initBtn")
     progressBar = document.getElementById("progressBar")
     progressBarValue = document.getElementById("progressBarValue")
     chunksLabel = document.getElementById("ChunksLabel")
     sizeLabel = document.getElementById("SizeLabel")
     speedLabel = document.getElementById("SpeedLabel")
     startBtn = document.getElementById("startBtn")
    initBtn.disabled = true
    startBtn.disabled = true
    fileBtn.addEventListener("change", () => {file = fileBtn.files[0];fileFlag=true})
    regBtn.addEventListener("click", () => {register()})
    chunkSizeInput.addEventListener("change", () => {changeChunkSize(chunkSizeInput, chunkSizeTypeInput)})
    chunkSizeTypeInput.addEventListener("change", () => {changeChunkSize(chunkSizeInput, chunkSizeTypeInput)})
    threadsInput.addEventListener("change", () => {threads = threadsInput.value})
    initBtn.addEventListener("click", () => {init()})
    startBtn.addEventListener("click", () => {start()})
  }
})