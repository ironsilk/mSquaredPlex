const express = require('express')
const app = express()
const stringhash = require('string-hash')
const fs = require('fs')
const Readable = require('stream').Readable
const convert = require('html-convert')({
  width       : 600,        // Note: This doesn't appear to work as per the docs
  height      : 200,
})
const bodyParser = require('body-parser')
const port = process.env.HTML_TO_IMAGE_PORT

app.use(express.static('public'))
app.use(bodyParser());

app.post('/make-image', function (req, res) {
  const html = req.body.html
  const force = req.body.force
  
  // Create a hash off the html
  // const hash = stringhash(html)
  const hash = 'image'
  const filename = `${hash}.png`
  const imagepath = `./public/${filename}`

  // See if the image has already been created
  if (force || !fs.existsSync(imagepath)) {
    // Else, we'll generate an image from the html
    const s = new Readable();
    s._read = function noop() {}; // Actually required
    s.push(html);
    s.push(null);

    const tmpFileStream = s.pipe(convert())
      .pipe(fs.createWriteStream(imagepath))
    tmpFileStream.on('finish', function () {
      res.send(filename)
    })
  } else {  
    res.send(filename)
  }
})

app.listen(port, function () {
  console.log(`Listening on port: ${port}`)
})
