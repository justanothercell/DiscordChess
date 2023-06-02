import os
import datetime
import contextlib
import discord
from dotenv import load_dotenv
from cairosvg import svg2png

import chess
import chess.svg

load_dotenv()

start_pos = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'

TOKEN = os.getenv('DISCORD_TOKEN')

client = discord.Bot(intents=discord.Intents.all(), activity=discord.Game(name='chess'))


@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return
    if not message.content.startswith('move'):
        return
    if message.reference is not None:
        ref_msg = await message.channel.fetch_message(message.reference.message_id)
        if ref_msg.author != client.user:
            return
        reference = ref_msg.content
    elif message.channel.type in [discord.ChannelType.public_thread, discord.ChannelType.private_thread]:
        history = await message.channel.history(limit=2).flatten()
        if len(history) != 2:
            return
        if history[1].type != discord.MessageType.thread_starter_message:
            return
        if history[1].author != client.user:
            return
        reference = history[1].system_content
    else:
        return
    
    ref_cntnt = reference.split('\n')[0]
    if not ref_cntnt.startswith('**FEN** `') or not ref_cntnt.endswith('`'):
        return
    pos = ref_cntnt[9:-1].strip()
    board = await try_board_from_fen(message, pos)
    if board is None:
        return
    moves = [m for m in message.content[4:].split() if len(m) > 0]
    for move in moves:
        try:
            board.push_san(move)
        except Exception as e:
            await respond(message, f'**Invalid move `{move}`**\n`{e}`')
            return
        
    with render_board(board, num_history=len(moves)) as img:
        action = f'Moved `{" ".join(moves)}`' if len(moves) > 0 else "Status"
        await respond_position(message, img, board, action)


@client.event
async def on_ready():
    print('--- Bot enabled ---')
    print(client.user.name)
    print(client.user.id)
    print(datetime.datetime.now())
    print('-------------------')


@client.slash_command(name='setup', description='Setup a new chess game')
async def setup(ctx, fen=None):
    pos = fen if fen is not None else start_pos
    board = await try_board_from_fen(ctx, pos)
    if board is None:
        return
    with render_board(board) as img:
        await respond_position(ctx, img, board, 'Set up game from FEN')

async def try_board_from_fen(ctx, fen):
    try:
        return chess.Board(fen)
    except Exception as e:
        await respond(ctx, f'**Invalid FEN**\n`{e}`', ephemeral=True)
        return None


@contextlib.contextmanager
def render_board(board, num_history=0):
    kwargs = {}
    if board.is_check():
        kwargs['check'] = board.king(chess.WHITE if board.turn else chess.BLACK)
    arrows = []
    for i, move in enumerate(board.move_stack[::-1][:num_history]):
        arrow = chess.svg.Arrow.from_pgn(move.uci())
        if i == 0:
            arrow.color = "green"
        else:
            arrow.color = "blue"
        arrows.append(arrow)
    img = chess.svg.board(
        board,
        size=350,
        arrows=arrows,
        **kwargs
    )
    svg2png(bytestring=img, write_to='position.png')
    with open(f'position.png', 'rb') as pic:
        yield discord.File(pic)


async def respond_position(ctx, img, board, action):
    await respond(ctx, f'**FEN** `{board.fen()}`\n**{action}**\n**{"White" if board.turn else "Black"} to play, move {board.fullmove_number}**', file=img)


async def respond(context, *args, **kwargs):
    if type(context) == discord.ApplicationContext:
        await context.respond(*args, **kwargs)
    else:
        kwargs['reference'] = context
        await context.channel.send(*args, **kwargs)

client.run(TOKEN)