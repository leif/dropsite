#!/usr/bin/env python3

"""
dropsite is yet-another imperfect answer to one of the most difficult questions
of our time: how can we transfer files between our computers (also known as the
XKCD#949 problem). Among other things, this can be useful for easily
transferring files from a mobile phone to a laptop, via a WiFi LAN or Tor.

dropsite could also be used in a less ephemeral configuration, providing a sort
of miniature document submission system with much less complexity, attack
surface, features, etc than SecureDrop and GlobaLeaks offer. But you shouldn't
use it for anything too important before some people besides the author have
looked for bugs in it :)

The only dependencies are flask (and its dependencies). I think this should run
anywhere you can "pip install flask", but I've only tried it on Debian using
their packages. On Debian stable with the testing repo enabled, you can run
these commands:

    sudo apt install python3-flask
    sudo apt install -t testing python3-werkzeug

(It's possible that the version of werkzeug in Debian stable will also work,
but I've made a number of changes since I last tried it. The version in Debian
testing fixed a lot of bugs and it installs on stable without requiring
anything else from testing, so I recommend using that.)

In the future perhaps I'll package this correctly for some definition of
correct so it can be installed in same way, but it's currently completely
stand-alone so you can just run it like this to see the help and some example
ways to use it:

    ./dropsite.py
"""

__author__  = "Leif Ryge"
__date__    = "2018-02-13"
__license__ = "none"
__version__ = "0"

import os
import time
import hashlib
import datetime
import subprocess
import click
from flask import Flask, request, Response
from werkzeug.exceptions import ClientDisconnected
from werkzeug.formparser import parse_form_data
from werkzeug.serving import run_simple
from werkzeug.utils import secure_filename

app = Flask(__name__)

# unnecessary, but makes this also work as subcommand of flask
register_flask_subcommand = lambda f: app.cli.command()(f) and f

@click.command()
@register_flask_subcommand
@click.option('-S', '--save-to',  help="Directory to save files to",
                                          type=click.Path(file_okay=False, dir_okay=True,
                                                          exists=True, writable=True,
                                                          resolve_path=True))
@click.option('-P', '--pipeline', help="Shell pipeline to process files through")
@click.option('-s', '--suffix',   help="String to append to filenames", default="")
@click.option('-p', '--port',     help="Port to listen on", default=8080)
@click.option('-H', '--host',     help="IP to listen on", default="127.0.0.1")
@click.option('-t', '--onion',    help="Create an ephemeral Tor onion service", is_flag=True)
@click.option('--serve-source',   help="Include a link to the source code", is_flag=True)
@click.pass_context
def dropsite(ctx, port, host, save_to, pipeline, suffix, onion, serve_source):
    """
This is a small application for receiving file uploads via HTTP. Uploaded files
can be passed through a shell pipeline and/or written to disk. Here are some
example usages:

\b
save files to the ./uploads directory:
    dropsite.py --save-to ./uploads

\b
same, but also encrypt files for user@host and append .gpg to filenames:
    dropsite.py -S ./uploads --pipeline 'gpg -er user@host' --suffix .gpg

\b
same, but compress files with gzip before encrypting:
    dropsite.py -S ./uploads -P 'gzip|gpg -er user@host' --suffix .gz.gpg

\b
rate-limit uploads to 20KB/sec, but don't actually save them:
    dropsite.py -P 'pv -L 20k' # pv also prints throughput
    """

    if serve_source:
        @app.route('/'+os.path.basename(__file__))
        def sourcecode():
            with open(__file__) as fh:
                return Response(fh.read(),mimetype='text/plain')

    if not any([save_to, pipeline]):
        print(dropsite.get_help(ctx))
        ctx.exit("error: You must specify at least one of -S/--save-to or -P/--pipeline.")

    if onion:
        if host != "127.0.0.1":
            ctx.exit("error: You may not run an onion when binding to a non-localhost ip")
        from stem.control import Controller
        with Controller.from_port() as controller:
            controller.authenticate()
            print("Creating ephemeral onion listener...")
            resp = controller.create_ephemeral_hidden_service({80:port}, await_publication=True, detached=True)
            print("Listening at http://%s.onion/" % (resp.service_id,))
            onion = resp.service_id

    app.config.update(
        dropsite=dict(pipeline=pipeline, save_to=save_to, suffix=suffix, serve_source=serve_source, onion_address=onion, bind_address=host))
    if app.debug:
        run_simple(host, port, app, use_reloader=True,)
    else:
        run_simple(host, port, app, threaded=True)

class HashPipeFileStream(object):

    """
    This class provides a file-like interface for werkzeug's parse_form_data to
    write uploaded files to.

    It will:
    1. pass itself to the register function, so that it can be cleaned up later
    2. (optionally) filter the file data through a shell pipeline
    3. (optionally) write the (possibly filtered) data to a file (optionally
       adding a suffix, and ensuring the name is unique)
    4. call a callback with the file's name, size, and hash when it is done
    """

    @classmethod
    def factory_factory(cls, register, dir_name, suffix, pipeline, callback, hash_fn):
        """
        This encloses all of the HashPipeFileStream parameters except for the
        filename in a function with the correct signature for werkzeug's
        stream_factory interface (which provides the filenames).
        """
        def stream_factory(total_content_length, content_type, filename, content_length=None):
            return cls(register, dir_name, filename, suffix, pipeline, callback, hash_fn, total_content_length)
        return stream_factory

    @staticmethod
    def ensure_unique(filename, suffix):
        """
        This ensures that the actual filename (with the server's suffix which
        is not exposed to the uploader) is unique by appending .N to it when
        necessary.

        It returns both the actual filename and the uploader's original
        filename with the same .N appended. Eg, if the uploader's filename is
        'foo', the suffix is '.bar', and the files foo{,.1,.2}.bar already
        exist, this will return ('foo.3', 'foo.3.bar').

        The uploader's filename should be sanitized and appended to the path to
        the upload directory prior to passing it here.
        """
        dup_count = 0
        actual_filename = filename + suffix
        while os.path.exists(actual_filename):
            dup_count += 1
            actual_filename = "%s.%s%s" % (filename, dup_count, suffix)
        if dup_count:
            return "%s.%s" % (filename, dup_count), actual_filename
        else:
            return filename, actual_filename

    def __init__(self, register, dir_name, filename, suffix, pipeline, callback, hash_fn, req_length):

        self.start_time = time.time()
        self.callback = callback
        self.hash = hash_fn()
        self.length = 0
        self.req_length = req_length
        self.done = False
        self.unsanitized_name = filename

        filename = secure_filename(filename) or 'bad_filename' # in case secure_filename returns ''
        
        if dir_name is None:
            self.filename = filename
            self.actual_filename = '/dev/null'

        else:
            filename = os.path.join(dir_name, filename)
            filename, actual_filename = self.ensure_unique(filename, suffix)

            self.filename = os.path.basename(filename)
            self.actual_filename = actual_filename

        self.fh = open(self.actual_filename, "wb")

        if pipeline is not None:
            self.proc = subprocess.Popen(pipeline, stdout=self.fh, stdin=subprocess.PIPE, shell=True)
        else:
            self.proc = None

        register(self)

    def cleanup(self):
        assert not self.done, "cleanup() called twice?"
        if self.proc:
            self.proc.communicate()
        self.fh.close()
        self.done = True

    def write(self, data):
        #print("writing %s bytes" % (len(data),))
        if self.proc:
            self.proc.stdin.write(data)
        else:
            self.fh.write(data)
        self.length += len(data)
        self.hash.update(data)

    def seek(self, a):
        assert a == 0, "this is solely for werkzeug to tell us it is done with seek(0)"
        self.cleanup()
        seconds = time.time() - self.start_time
        if self.unsanitized_name == "" and self.length == 0:
            os.unlink(self.actual_filename)
            return
        self.callback( dict(actual_filename = self.actual_filename,
                            filename        = self.filename,
                            length          = self.length,
                            hash            = self.hash.hexdigest(),
                            seconds         = seconds,
                            kbps            = self.length/seconds/1024) )

@app.route("/", methods=["GET", "POST"])
def endpoint():

    config = app.config['dropsite']

    if request.method == 'GET':
        return T_PAGE % (T_FORM +
                         ('<p><a href=%s>source code</a></p>' % os.path.basename(__file__)
                          if config['serve_source'] else ''))

    if request.method == 'GET':
        return T_PAGE % (T_FORM +
                         ('<p>curl -F upload=@./YOURFILENAMEHERE {0}</p>'.format(resp.service_id)
                          if config['serve_source'] else ''))

    dir_name = None

    if config['save_to']:
        dir_name = os.path.join(config['save_to'], datetime.datetime.now().isoformat().replace(':','-'))
        assert not os.path.exists(dir_name), "%s existing was unexpected" % (dir_name,)
        os.mkdir(dir_name)

    results, open_streams = [], []

    def callback(res):
        results.append(res)
        print("OK: {filename!r} ({length} bytes @ at {kbps:.1f} KB/s) -> {actual_filename!r}".format(**res))

    factory = HashPipeFileStream.factory_factory(
                register = open_streams.append,
                callback = callback,
                dir_name = dir_name,
                pipeline = config['pipeline'],
                suffix   = config['suffix'],
                hash_fn  = hashlib.sha256
                )

    try:
        stream, form, files = parse_form_data(request.environ, stream_factory=factory)

    except ClientDisconnected:
        for stream in open_streams:
            if stream.done:
                continue
            stream.cleanup()
            _, partial_name = stream.ensure_unique(stream.actual_filename, '.partial')
            os.rename(str(stream.actual_filename), str(partial_name))
            print("FAIL: during a supposed %s byte request, client disconnected after writing %s bytes of %r to %r" % (
                    stream.req_length, stream.length, stream.filename, partial_name))
        raise

    if 'note' in form:
        for note in form.getlist('note'):
            if len(note):
                fh = factory(None, None, 'note.txt', None)
                fh.write(bytes(note+"\n",'utf-8'))
                fh.seek(0)

    if results:
        return T_PAGE % (T_DONE % "\n".join(T_RESULT.format(**res) for res in results))
    else:
        print("FAIL: empty submission")
        os.rmdir(dir_name)
        return "It appears that you submitted neither a file nor a note.\n"


T_PAGE="""<!doctype html>
<head>
<title>dropsite</title>
<style type="text/css">
body {
margin: 2em;
font-family: Monospace;
font-size: smaller;
}
h1 { border-bottom:1px solid black }
th { text-align: left; padding-right:2em; border-bottom:1px solid black}
td { background: #ddd; padding:.5em; }
</style>
</head>
<body>%s</body>
"""

T_FORM="""
<h1>dropsite</h1>
<form method=post enctype=multipart/form-data>
<h2>step 1: type a message and/or select file(s) to upload</h2>
<textarea name=note cols=72 rows=5></textarea>
<br><br>
<input type=file name=file multiple=multiple>
<h2>step 2: click the send button</h2>
<input type=submit value=send>
</form>
"""

T_RESULT="""<tr> <td>{filename}</td> <td>{length}</td> <td>{kbps:.1f}</td> <td>{seconds:.1f} seconds</td>
<td>{hash}</td>
</tr>
"""

T_DONE="""
<h1>upload successful</h1>
<table>
 <tr><th>Filename</th><th>Bytes</th><th>KB/sec</th><th>Time</th><th>SHA256</th></tr>
%s
</table>
<p><a href="/">Back</a></p>
"""

if __name__ == "__main__":
    dropsite()

"""
some werkzeug annoyances i encountered while writing this:

    - parse_form_data calls stream_factory for each file, but returns a files
      dictionary keyed by filename so if multiple files with the same name are
      uploaded only the first gets included in the files object (even though
      the other stream factories were called and their streams written to).
      but this doesn't affect us because of the results.append callback
      tomfoolery we had to do for other reasons.

    - parse_form_data parses *lines* internally, so write() gets called on the
      stream object twice per line (the second time being a \n or \r or \r\n)
      this is irritating but doesn't really matter, i guess?

    - the signature of werkzeug's default_stream_factory has its arguments in
      the wrong order (it doesn't use them, so it doesn't matter). (TODO: PR)

known warts/issues/irritations maybe worth fixing:

    - submissions with no file create and then delete a bad_filename file

    - submissions with no file and no note create and then delete a directory

    - Probably callback should receive the stream object instead of having
      HashPipeFileStream create a result dict.

    - It would be nice to print something when an upload starts instead of just
      when it finishes. A register function could easily do that, but the above
      warts around handling of POSTs without a file get in the way (the browser
      sends an empty part with filename=""). Part of the complexity is caused
      by my desire to save uploaded files that have no name as "bad_filename";
      perhaps that isn't worth doing.
    
    - the KB/sec of the note displayed in the results page isn't measuring
      network throughput at all as the note was fully received before its
      HashPipeFileStream object was created. So, it is actually the length of
      the note divided by the time taken to write it through the pipeline
      (which in the case of a short note is a relatively low number of KB/sec).
      This is potentially confusing.

    - If a file called note.txt is uploaded, the note supplied in the note
      field will be saved as note.txt.1

    - Generally uploaders should not be able to determine if a pipeline is
      being used and/or if the --save-to option is used, but there is a
      side-channel by which they can tell if --save-to is being used: when it
      isn't, if they submit a request with two files with the same name
      (i think not possible via the browser, but easy with curl) then the
      results page will show their results without appending .1 to the second
      instance of the filename.

todo:
    - add --serve-directory (download support)?
    - add random-length low-entropy hidden form field for padding
        - assuming responses are compressed but requests aren't, I think this
          will obscure the upload filesize?
    - add optional javascript, XHR progress bar?
    - add curl upload instructions to html?
      (it's curl -F foo=@./filename to upload ./filename)
    - .desktop file to launch in xterm for use as a desktop app
        - and/or maybe a gtk ui?
    - systemd unit file for use as a daemon
    - python packaging
    - debian packaging
    - test on tails
    - think about dos mitigation, especially in the context of small computers
      running this
    - debian armhf image builder

"""
