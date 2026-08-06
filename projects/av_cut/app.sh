#! /bin/sh

$webdoc --document --language "English"
$webdoc --populate --document --head
$webdoc --populate --head \
	--title "Media cutter"
$webdoc --populate --head \
	--meta --usual-meta-stuff
$webdoc --populate --document --body

$webdoc --embed --css-section
$webdoc --embed --js-section

$webdoc --populate --body --header
$webdoc --populate --body --main
$webdoc --populate --body --footer

$webdoc --populate --header \
	--heading "Media cutter"
$webdoc --populate --main \
	--main-container
$webdoc --populate --footer \
	--copyright-notice --placeholder

$webdoc --populate --main-container \
	--tabs
$webdoc --populate --tabs --tab \
	--media-input
$webdoc --populate --tabs --tab \
       	--param-select
$webdoc --populate --tabs --tab \
	--preview-edit
$webdoc --populate --tabs --tab \
	--data-output

$webdoc --populate --media-input \
	--radio-group
$webdoc --populate --radio-group --radio \
	--upload-media-file --show-widget
$webdoc --populate --radio-group --radio \
	--enter-yt-url --show-widget
$webdoc --populate --param-select \
	--select --transcription-engine
$webdoc --populate --param-select \
	--select --media-language
$webdoc --populate --param-select \
	--select --model-size
$webdoc --populate --preview-edit \
	--video-preview
$webdoc --populate --preview-edit \
	--cutting-handles
$webdoc --populate --preview-edit \
	--text-edit --time-ammounts
$webdoc --populate --preview-edit \
	--submit-button --perform-cutting
$webdoc --populate --data-output \
	--ordered-list \
	--media-outfiles-to-dl
$webdoc --populate --data-output \
	--zipfile-to-dl

system() {
cat <<ENDS
You are a specification
	parser and translator to code.
You have to generate safe code.
If in doubt, err on safety.
Try hard to find out user spec's intent.
When in doubt, use (or simulate)
	common sense.
Share only the source files.
ENDS
}

prompt() {
cat <<ENDP
In this (pseudo-)bash spec, try to
	understand the specifications
	and generate a Flask app
	with the INTENDED functionality.
Share app.py (with embedded HTML)
	and requirements.txt.
Use external libraries,
	when needed.
Use your "creativity" for styling the app.
Use dark theme.
The app listens to port 5045.
ENDP
}
