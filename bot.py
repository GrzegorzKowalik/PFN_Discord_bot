import json
import asyncio
import discord
import glob
import re
import tempfile
import os.path
import time
import hashlib

from PIL import Image


try:
    with open('config.json') as f:
        config = json.load(f)
        assert("token" in config)
        assert("watch_dir" in config)
        assert("cache_file" in config)
        assert("channel_id" in config)
except FileNotFoundError:
    print("No config file found (config.json)")
    exit(2)


cache = []


def load_cache():
    global cache
    cache_file_path = config['cache_file']
    if not os.path.isfile(cache_file_path):
        generate_cache_file(cache_file_path)
    with open(cache_file_path) as f:
        cache = json.load(f)


def generate_cache_file(file_path):
    files = get_fireball_photos()
    cache = []
    for path in files:
        cache.append(create_cache_entry(path))

    with open(file_path, "w+") as cache_file:
        json.dump(cache, cache_file)


def create_cache_entry(path):
    date, time = get_date_time_from_name(path)
    ref = hashlib.md5(path.encode()).hexdigest()[:10]
    entry = {
        "name": path.split('/')[-1],
        "path": path,
        "date": date,
        "time": time,
        "ref": ref
    }
    return entry


def get_date_time_from_name(path):
    filename = path.split('/')[-1]
    date = filename[1:5] + "-" + filename[5:7] + "-" + filename[7:9]
    time = filename[10:12] + ":" + filename[12:14] + ":" + filename[14:16]
    return date, time


def get_fireball_photos():
    dir_path = config['watch_dir']
    files = glob.glob(dir_path + "/**", recursive=True)
    if len(files) == 0:
        raise RuntimeError("No observations found in specified watch_dir")
    files = {f.replace("\\","/") for f in files}
    regex = re.compile(".*_P\.bmp")
    files = {f for f in files if regex.match(f)}
    files = {f for f in files if "_110000_" not in f and
                                 "_110001_" not in f and
                                 "_230000_" not in f and
                                 "_230001_" not in f}
    return files


def filter_new_findings():
    cached_files = {c['path'] for c in cache}
    current_files = get_fireball_photos()
    return list(current_files - cached_files)


def convert_bmp_to_jpg(bmp_path):
    img = Image.open(bmp_path)
    tmp_dir = tempfile.gettempdir()
    png_filename = tmp_dir + "\pfn_png_tmp_{}.png".format(time.time())
    img.save(png_filename, "png")
    return png_filename


def add_to_cache(path):
    global cache
    cache_file_path = config['cache_file']
    entry = create_cache_entry(path)
    cache.append(entry)
    with open(cache_file_path, "w") as f:
        f.write(json.dumps(cache))
    return entry


token = config['token']
client = discord.Client()
channel = discord.Object(id=config['channel_id'])


async def background_task():
    global cache

    while not client.is_closed:
        await asyncio.sleep(60)
        findings = filter_new_findings()

        if len(findings) == 0:
            continue
        if len(findings) == 1:
            entry = add_to_cache(findings[0])
            photo = convert_bmp_to_jpg(entry['path'])
            await client.send_message(channel, content="Znalazłem!\nData: {}\nGodzina: {}\nRef: {}".format(entry['date'], entry['time'], entry['ref']))
            await client.send_file(channel, photo)
        if len(findings) > 1:
            msg = "Znalazłem trochę więcej meteorów...\n"
            for f in findings:
                entry = add_to_cache(f)
                msg += "Ref: {}\n".format(entry['ref'])
            await client.send_message(channel, content=msg)


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('!pfnbot ref '):
        ref = message.content.split(' ')[2]
        entries = [c for c in cache if c['ref'] == ref]
        if not entries:
            await client.send_message(channel, content="Nie znalazłem detekcji o podanym refie")
            return
        elif len(entries) == 1:
            entry = entries[0]
            photo = convert_bmp_to_jpg(entry['path'])
            await client.send_file(channel, photo)
        else:
            await client.send_message(channel, content="Ochuj :o")
        return

    if message.content.startswith('!pfnbot'):
        msg = 'No żyję, spokojnie. Nic nie wrzucam bo nic nie spada, może chmury?'.format(message)
        await client.send_message(message.channel, msg)
        return


@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')
    print('Reading cache file')
    load_cache()
    # await client.send_message(channel, "Witam, właśnie ożyłem i będę tutaj wrzucał zdjęcia zrobione przez PFN")


client.loop.create_task(background_task())
client.run(token)
