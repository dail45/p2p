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

function renderError(e) {
  console.log(e)
}

async function search() {
  searchBtn.disabled = true
  try {
    response = await fetch(`info/${rnum}`)
  } catch (e) {
    if (response.statusText === String(500)) {
      renderError("Internal Server Error")
      setTimeout(() => {searchBtn.disabled = false}, 500)
      return
    }
    renderError("Connection Error")
    setTimeout(() => {searchBtn.disabled = false}, 500)
    return
  }
  try {
    res = await response.json()
  } catch (e) {
    renderError("Internal Server Error")
    setTimeout(() => {searchBtn.disabled = false}, 500)
    return
  }
  filename = res["filename"]
  filenameLabel.innerText = `filename: ${res["filename"]}`
  totallength = parseInt(res["totallength"])
  chunkSize = parseInt(res["chunksize"])
  renderChunksAndSize(0, 0)
  saveBtn.disabled = false
  setTimeout(() => {searchBtn.disabled = false}, 500)
}

var fileStream
async function save() {
  var fileHandle = await window.showSaveFilePicker({suggestedName: filename})
  fileStream = await fileHandle.createWritable()
  // await fileStream.write(new Blob(["ПОШЁЛ ТЫ НАХЕР КОЗЁЛ!!!"], {type: "text/plain"}))
  // await fileStream.close()
  startBtn.disabled = false
}

// async function init() {
//   if (fileFlag === false) {
//     return
//   }
//   regBtn.disabled = true
//   initBtn.disabled = true
//   startBtn.disabled = true
//   let data = {
//     "chunksize": chunkSize,
//     "threads": threads,
//     "RAM": 64 * (2 ** 20),
//     "filename": file.name,
//     "totallength": file.size
//   }
//   let sendJson = JSON.stringify(data)
//   response = await fetch(`/start/${rnum}`, {
//     method: "POST",
//     body: sendJson
//   })
//   let log = await response.json()
//   console.log(log)
//   setTimeout(() => {if (startFlag === false) {regBtn.disabled = false;initBtn.disabled = false}}, 500)
//   startBtn.disabled = false
// }

async function start() {
  rnumInput.disabled = true
  searchBtn.disabled = true
  startBtn.disabled = true
  startFlag = true
  writeChunksThread()
  renderSpeed()
  startThread(Math.ceil(totallength / chunkSize))
}


async function startThread(totalchunks) {
  while (doneFlag === false) {
    if (threadsOn >= threads) {
      setTimeout(async () => {
        await startThread()
      }, 50)
      return
    }
    threadsOn++
    await getChunk()
    if (downloaded === totalchunks) {
      doneFlag = true
    }
  }
}

async function getChunk() {
  while (true) {
    try {
      response = await fetch(`/awaitChunk/${rnum}`)
    } catch (e) {
      if (response.statusText === String(500)) {
        renderError("Internal Server Error")
        return
      }
      renderError(e)
      return
    }
    try {
      res = await response.json()
    } catch (e) {
      renderError("Internal Server Error")
      return
    }
    if (res["status"] === "dead" || res["status"] === "dead-timeout") {
      return
    } else if (res["status"] === "alive-timeout") {
      continue
    } else if (res["status"] === "alive") {
      let cnum = res["cnum"]
      try {
        response = await fetch(`/downloadChunk/${rnum}?index=${cnum}`)
        const reader = response.body.getReader()
        let chunks = []
        let lenchunks = 0
        while (true) {
          const {done, value} = await reader.read()
          if (done) {
            break
          }
          // renderSpeed
          downloadedBytes += value.length
          lenchunks += value.length
          chunks.push(value)
          console.log(1)
        }

        chunk = new Uint8Array(lenchunks)
        let pos = 0
        for (let part of chunks) {
          chunk.set(part, pos)
          pos += part.length
        }

        downloaded += 1
        STORAGE[cnum] = chunk
        console.log(`downloaded: ${chunk.length}, in storage: ${STORAGE[cnum].length}, dwBytes: ${downloadedBytes}`)
        STORAGELIST.push(cnum)
        return
      } catch (e) {
        if (response.statusText === String(500)) {
          renderError("Internal Server Error")
          return
        }
        renderError(e)
        return
      }

    }
  }
}

async function writeChunksThread() {
    if (STORAGELIST.length > 0) {
      let cnum = STORAGELIST.pop()
      let chunk = STORAGE[cnum]
      await fileStream.seek(cnum * chunkSize)
      await fileStream.write(chunk)
      console.log(`seek at ${cnum * chunkSize} and write ${chunk.length}`)
      delete STORAGE[cnum]
    }
    if (doneFlag === false || STORAGELIST.length > 0) {
      setTimeout(writeChunksThread, 50)
    } else {
      await fileStream.close()
    }
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
  }
  if (value > 100) {
      value = 100
    } else {
      value = 1 * value
    }
  var progressBarValue = document.getElementById("progressBarValue")
  progressBarValue.innerText = `${value} %`
}

function renderChunksAndSize(chunks, size) {
  chunksLabel.innerText = `${chunks}/${Math.ceil(totallength / chunkSize)}Ch  `
  var formatedSize = formatSize(totallength)
  var sizeDone = formatSize(size, power=formatedSize[2])
  sizeLabel.innerText = `${sizeDone[0]}/${formatedSize[0]}${formatedSize[1]}  `
}

var downloadSpeedArray = Array().concat()
var lastSize = 0
var speed = 0
var counter = 0
function renderSpeed(flag=false) {
  if (flag === false) {
    setTimeout(renderSpeed, 500, true)
    return
  }
  counter++
  downloadSpeedArray.push((downloadedBytes - lastSize) / 0.5)
  lastSize = downloadedBytes
  if (downloadSpeedArray.length > 6) {
    downloadSpeedArray.shift()
  }
  console.log(downloadSpeedArray)
  speed = downloadSpeedArray.reduce((partialSum, a) => partialSum + a, 0)
  speed /= downloadSpeedArray.length
  formatedSpeed = formatSize(speed)
  struct = {
    "downloadedSpeedArray": downloadSpeedArray,
    "lastSize": lastSize,
    "downloadedBytes": downloadedBytes,
    "speed": speed,
    "formatedSpeed": formatedSpeed
  }
  console.log(struct)
  speedLabel.innerText = `${formatedSpeed[0]} ${formatedSpeed[1]}/s`
  renderChunksAndSize(downloaded, downloadedBytes)
  renderProgressBar(Math.ceil((downloadedBytes / totallength) * 100))
  if (doneFlag === false) {
    setTimeout(renderSpeed, 500, false)
  }
}


var filename
var fileFlag = false
// var regFlag = false
// var initFlag = false
// var startFlag = false
var doneFlag = false
var rnum = 0
var file = null
var state = 0
var chunkSize = 4 * (2 ** 20)
var threads = 16
var threadsOn = 0
var totallength = 0
var downloaded = 0
var downloadedBytes = 0

var STORAGE = {}
var STORAGELIST = []

var filenameInput = document.getElementById("filenameInput")
var searchBtn = document.getElementById("searchBtn")
var saveBtn = document.getElementById("saveBtn")
var progressBar = document.getElementById("progressBar")
var progressBarValue = document.getElementById("progressBarValue")
var chunksLabel = document.getElementById("ChunksLabel")
var sizeLabel = document.getElementById("SizeLabel")
var speedLabel = document.getElementById("SpeedLabel")
var startBtn = document.getElementById("startBtn")
var filenameLabel = document.getElementById("filenameLabel")
var rnumInput = document.getElementById("rnumInput")

document.addEventListener("readystatechange", () => {
  if (document.readyState === "complete") {
    renderProgressBar(0)
    filenameInput = document.getElementById("filenameInput")
    searchBtn = document.getElementById("searchBtn")
    saveBtn = document.getElementById("saveBtn")
    progressBar = document.getElementById("progressBar")
    progressBarValue = document.getElementById("progressBarValue")
    chunksLabel = document.getElementById("ChunksLabel")
    sizeLabel = document.getElementById("SizeLabel")
    speedLabel = document.getElementById("SpeedLabel")
    startBtn = document.getElementById("startBtn")
    filenameLabel = document.getElementById("filenameLabel")
    rnumInput = document.getElementById("rnumInput")

    saveBtn.disabled = true
    startBtn.disabled = true

    searchBtn.addEventListener("click", () => {search()})
    rnumInput.addEventListener("change", () => {rnum = parseInt(rnumInput.value)})
    saveBtn.addEventListener("click", () => {save()})
    startBtn.addEventListener("click", () => {start()})



    /*fileBtn.addEventListener("change", () => {file = fileBtn.files[0];fileFlag=true})
    regBtn.addEventListener("click", () => {register()})
    chunkSizeInput.addEventListener("change", () => {changeChunkSize(chunkSizeInput, chunkSizeTypeInput)})
    chunkSizeTypeInput.addEventListener("change", () => {changeChunkSize(chunkSizeInput, chunkSizeTypeInput)})
    threadsInput.addEventListener("change", () => {threads = threadsInput.value})
    initBtn.addEventListener("click", () => {init()})
    */
  }
})