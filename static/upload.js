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

function formatSize(size, power=0) {
  let newSize = size
  let typeSize = "B"
  let typeSizeInt = 0
  if (newSize >= 1024 || power > 0) {
    newSize /= 1024
    typeSize = "KB"
    typeSizeInt++
  }
  if (newSize >= 1024 || power > 1) {
    newSize /= 1024
    typeSize = "MB"
    typeSizeInt++
  }
  if (newSize >= 1024 || power > 2) {
    newSize /= 1024
    typeSize = "GB"
    typeSizeInt++
  }
  return [parseFloat(newSize.toFixed(2)), typeSize, typeSizeInt]
}

async function register() {
  regBtn.disabled = true
  startBtn.disabled = false
  response = await fetch("/reg")
  rnum = await response.text()
  document.getElementById("rnumLabel").innerText = "rnum: " + rnum
  setTimeout(() => {regBtn.disabled = false}, 500)
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
  setTimeout(() => {regBtn.disabled = false;initBtn.disabled = false}, 500)
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
      uploadedBytes += chunk.byteLength
      renderProgressBar(Math.ceil((uploadedBytes / file.size) * 100))
      renderChunksAndSizeAndSpeed(uploaded, uploadedBytes)
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

function renderProgressBar(value) {
  var canvas = document.getElementById("progressBar")
  if (canvas.getContext) {
    var ctx = canvas.getContext("2d")
    ctx.fillStyle = "#BBBBBB"
    ctx.fillRect(0, 0, canvas.width,20)
    ctx.fillStyle = "#202020"
    ctx.fillRect(1, 1, canvas.width - 2, 18)
    ctx.fillStyle = "#05B8CC"
    if (value > 100) {
      width = 100
    } else {
      width = 1 * value
    }
    ctx.fillRect(1, 1, width, 18)
    console.log(canvas.height, canvas.width)
  }
  if (value > 100) {
      value = 100
    } else {
      value = 1 * value
    }
  var progressBarValue = document.getElementById("progressBarValue")
  progressBarValue.innerText = `${value} %`
}

function renderChunksAndSizeAndSpeed(chunks, size) {
  chunksLabel.innerText = `${chunks}/${Math.ceil(file.size / chunkSize)}Ch  `
  var formatedSize = formatSize(file.size)
  var sizeDone = formatSize(size, power=formatedSize[2])
  sizeLabel.innerText = `${sizeDone[0]}/${formatedSize[0]}${formatedSize[1]}  `
}


var fileFlag = false
var regFlag = false
var initFlag = false
var doneFlag = false
var rnum = 0
var file = null
var chunkSize = 4 * (2 ** 20)
var threads = 16
var threadsOn = 0
var uploaded = 0
var uploadedBytes = 0
var speed = 0
var fileBtn = document.getElementById("uploadbtn")
var regBtn = document.getElementById("regBtn")
var chunkSizeInput = document.getElementById("numberChunkSizeInput")
var chunkSizeTypeInput = document.getElementById("typeChunkSizeSelect")
var threadsInput = document.getElementById("threadCountInput")
var initBtn = document.getElementById("initBtn")
var progressBar = document.getElementById("progressBar")
var progressBarValue = document.getElementById("progressBarValue")
var chunksLabel = document.getElementById("ChunksLabel")
var sizeLabel = document.getElementById("SizeLabel")
var speedLabel = document.getElementById("SpeedLabel")
var startBtn = document.getElementById("startBtn")

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