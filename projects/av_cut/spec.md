# Media editing app

## DOM structure

html
  language "en"
  charset "utf-8"
  title "Media editor"
  embed css-style
  embed js-script
  body
    header
      h2 "Media editor"
    main
      main-container
        tabs
          tab "load media"
            radio ["upload-file", "enter-url"]
            union
              input [type="file"]
              input [type="url"]
                checkbox use-browser-cookies
            submit-btn "load-file"
          tab "preview and cut"
            sync elements
              optional
                video-preview
              cut-handles
              cut-timers
              submit-btn "add-chunk"
              ul chunk-list
          tab "transcription controls"
            select ["openai-whisper", "faster", "mlx"]
            select ["de", "en", "fr", "ro"]
            select ["cpu", "cuda", "metal"]
            select model-size
            checkbox diarize
              checkbox piannote
              checkbox ai-api
                select ["gemini", "claude"]
              checkbox name-speakers
                union
                  checkbox speaker-numbers
                  input[type="ol"] speaker-names
              checkbox api-key
                input[type="text"]
            submit-btn "transcribe"
          tab "extract results"
            textarea "transcription preview"
            submit-btn "download transcription"
            submit-btn "download zip-file"
    footer
      copyright-notice
        placeholder

## Remarks

- Try to guess my intent, even if ambiguous specs
- Avoid conflicting settings, wrong input, by disabling or hiding some elements dinamically
- Be creative, human-like when you use fonts, colors etc
- each tab has all its stuff in its own container, which fits horizontally, but overflow-y: auto
- responsive layout, optimized for MacBook and mobile
- dark theme
- do not scroll vertically the main container; innstead fit in browser page

## System prompt

You are an AI coder.
Logical corectness is paramount; when in doubt, err on safety.
Share only source ccode.

## Prompt

Please write a media editing Flask app following these requirements. Provide only requested features.
Share only source code: app.py (with embedded html), requirements.txt

