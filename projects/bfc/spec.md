# Document processing and converting utility

Please write a document processing and converting utility Flask app with embedded HTML.
It should support usual document formats, including PDF, EPUB among other.

Functional correctness is paramount. When in doubt, err on safety.
Guess my intent even when my specs are ambiguous.

## HTML Document layout (sketch)

html
  language en
  encoding utf-8
  title "Document Utilities"
  embed css, js
 body
   header h2 "Document Utilities"
   main container tabs
     tab "Document"
       drop area
       submit-btn upload
      tab "choose operation"
        select
          "Convert to other format"
          "Split by page/ranges"
          "Split smart by chapters, using AI API"
          "Make an extremely detailed TOC, using AI API"
      tab "choosen operation controls"
        // Multiplex for each chosen operation, keeping the current one
        checkbox use-API
          select ["Gemini", "Claude"]
          checkbox enter-apikey
            text[input="password"]
        html-elements designed by you for the operation
      tab "Results"
        optional
          textarea previews and results
          copy button
        optional
          downloadable artifacts
          submit-btn download \+
        submit-btn download all
  footer copyright-notice placeholder
