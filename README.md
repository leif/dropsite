This is a small application for receiving file uploads via HTTP. Uploaded files
can be passed through a shell pipeline and/or written to disk. Here are some
example usages:

save files to the ./uploads directory:

    dropsite.py --save-to ./uploads

same, but also encrypt files for user@host and append .gpg to filenames:

    dropsite.py -S ./uploads --pipeline 'gpg -er user@host' --suffix .gpg

same, but compress files with gzip before encrypting:

    dropsite.py -S ./uploads -P 'gzip|gpg -er user@host' --suffix .gz.gpg

rate-limit uploads to 20KB/sec, but don't actually save them:

    dropsite.py -P 'pv -L 20k' # pv also prints throughput
