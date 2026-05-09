import discord
import uuid
import random
from discord.ext import commands
from discord import app_commands
from discord.ext import tasks
from datetime import datetime


alarms = []
alarm_channels = {}
alarm_images = [
    "https://media.discordapp.net/attachments/1502335334971736204/1502490623599443978/i1136308537.png",
    "https://media.discordapp.net/attachments/1502335334971736204/1502490787605250192/i1643888808.png",
    "https://media.discordapp.net/attachments/1502335334971736204/1502490934963601532/i1365939250.png",
    "https://media.discordapp.net/attachments/1502335334971736204/1502490947550974083/i1317398511.png",
    "https://media.discordapp.net/attachments/1502335334971736204/1502491085367410748/i1669126352.png",
    "https://media.discordapp.net/attachments/1502335334971736204/1502491121115467928/i1324850964.png",
]

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


def normalize_time(t: str) -> str:

    t = t.strip().upper()

    # PM 1:30 → PM 01:30
    parts = t.split()

    if len(parts) != 2:
        return t  # 잘못된 입력은 그대로 (나중에 에러 처리 가능)

    ampm, clock = parts

    h, m = clock.split(":")

    h = int(h)

    return f"{ampm} {h:02d}:{m}"

class AlarmDetailView(discord.ui.View):

    def __init__(self, alarm_id):
        super().__init__(timeout=None)
        self.alarm_id = alarm_id

    @discord.ui.button(label="수정", style=discord.ButtonStyle.gray)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):

        alarm = next((a for a in alarms if a["id"] == self.alarm_id), None)

        if alarm is None:
            await interaction.response.send_message("삭제된 알림이에요.", ephemeral=True)
            return

        await interaction.response.send_modal(
            RegisterModal(alarm=alarm, alarm_id=self.alarm_id)
        )

    @discord.ui.button(label="삭제", style=discord.ButtonStyle.red)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):

        alarm = next((a for a in alarms if a["id"] == self.alarm_id), None)

        if alarm:
            alarms.remove(alarm)

            await interaction.channel.send(
                f"{interaction.user.mention}가 '{alarm['title']}' 알림을 삭제했어요."
            )

        await interaction.response.send_message("삭제 완료", ephemeral=True)

class AlarmButton(discord.ui.Button):

    def __init__(self, alarm_id, title):
        super().__init__(
            label=title,
            style=discord.ButtonStyle.blurple
        )
        self.alarm_id = alarm_id

    async def callback(self, interaction: discord.Interaction):

        alarm = next((a for a in alarms if a["id"] == self.alarm_id), None)

        if alarm is None:
            await interaction.response.send_message("삭제된 알림이에요.", ephemeral=True)
            return

        embed = discord.Embed(
            title=alarm["title"],
            color=discord.Color.blue()
        )

        embed.add_field(name="내용", value=alarm["content"], inline=False)
        embed.add_field(name="날짜", value=alarm["date"], inline=True)
        embed.add_field(name="시간", value=alarm["time"], inline=True)
        embed.add_field(name="대상", value=alarm["mentions"], inline=False)

        view = AlarmDetailView(self.alarm_id)

        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )

class AlarmView(discord.ui.View):

    def __init__(self, alarms_list):
        super().__init__(timeout=None)

        for alarm in alarms_list:
            self.add_item(AlarmButton(alarm["id"], alarm["title"]))

    @discord.ui.button(label="상세 보기", style=discord.ButtonStyle.blurple)
    async def detail(self, interaction: discord.Interaction, button: discord.ui.Button):

        if self.index >= len(alarms):
            await interaction.response.send_message("삭제된 알림이에요.", ephemeral=True)
            return

        alarm = alarms[self.index]

        embed = discord.Embed(
            title=alarm["title"],
            color=discord.Color.blue()
        )

        embed.add_field(name="내용", value=alarm["content"], inline=False)
        embed.add_field(name="날짜", value=alarm["date"], inline=True)
        embed.add_field(name="시간", value=alarm["time"], inline=True)
        embed.add_field(name="대상", value=alarm["mentions"], inline=False)

        await interaction.response.send_message(embed=embed, view=AlarmDetailView(self.index), ephemeral=True)

@tasks.loop(seconds=20)
async def check_alarm():

    now = datetime.now()

    current_dt = datetime.strptime(
        now.strftime("%y/%m/%d %p %I:%M"),
        "%y/%m/%d %p %I:%M"
    )

    remove_list = []

    for alarm in alarms:

        try:
            alarm_dt = datetime.strptime(
                f"{alarm['date']} {alarm['time']}",
                "%y/%m/%d %p %I:%M"
            )
        except:
            continue

        if alarm_dt <= current_dt:

            embed = discord.Embed(
                title=alarm["title"],
                description=f"{alarm['date']} {alarm['time']}",
                color=discord.Color.from_rgb(64, 224, 208)
            )

            embed.add_field(
                name="내용",
                value=alarm["content"],
                inline=False
            )

            embed.set_footer(text="알림 시스템")

            embed.set_image(url=random.choice(alarm_images))

            mentions = " ".join(f"<@{u.strip()}>" for u in alarm["targets"])

            guild_id = alarm["guild_id"]

            if guild_id not in alarm_channels:
                continue

            try:
                channel = await bot.fetch_channel(alarm_channels[guild_id])
            except:
                continue

            await channel.send(
                content=f"# 알림이 왔어요!\n{mentions}",
                embed=embed
            )

            remove_list.append(alarm)

    for alarm in remove_list:
        alarms.remove(alarm)

class RegisterModal(discord.ui.Modal):

    def __init__(self, alarm=None, alarm_id=None):
        super().__init__(title="알림 등록")

        self.alarm = alarm
        self.alarm_id = alarm_id

        def safe(v):
            return v if v is not None else ""

        self.title_input = discord.ui.TextInput(
            label="제목",
            placeholder="예) 동아리 팀 프로젝트 마감 기한",
            max_length=100,
            default=safe(alarm["title"] if alarm else "")
        )

        self.content_input = discord.ui.TextInput(
            label="내용",
            style=discord.TextStyle.paragraph,
            max_length=500,
            default=safe(alarm["content"] if alarm else "")
        )

        self.date_input = discord.ui.TextInput(
            label="날짜",
            placeholder="28/01/10",
            max_length=20,
            default=safe(alarm["date"] if alarm else "")
        )

        self.time_input = discord.ui.TextInput(
            label="시간",
            placeholder="AM 06:30 (형식 반드시 지켜주세요!)",
            max_length=20,
            default=safe(alarm["time"] if alarm else "")
        )

        self.target_input = discord.ui.TextInput(
            label="멘션 대상",
            placeholder="사용자 ID를 복사해서 입력하세요!",
            max_length=200,
            default=",".join(alarm["targets"]) if alarm else ""
        )

        self.add_item(self.title_input)
        self.add_item(self.content_input)
        self.add_item(self.date_input)
        self.add_item(self.time_input)
        self.add_item(self.target_input)

    async def on_submit(self, interaction: discord.Interaction):
        time_value = self.time_input.value.strip().upper()
        date_value = self.date_input.value.strip()

        try:
            datetime.strptime(f"{date_value} {time_value}", "%y/%m/%d %p %I:%M")
        except:
            await interaction.response.send_message(
                "형식 오류 (예: 28/01/10 AM 06:30)",
                ephemeral=True
            )
            return

        alarm_data = {
            "id": self.alarm_id if self.alarm_id else str(uuid.uuid4()),
            "title": self.title_input.value,
            "content": self.content_input.value,
            "date": date_value,
            "time": time_value,
            "targets": self.target_input.value.split(","),
            "mentions": " ".join(f"<@{u.strip()}>" for u in self.target_input.value.split(",")),
            "guild_id": interaction.guild.id
        }

        if self.alarm is None:
            alarms.append(alarm_data)
        else:
            index = next(i for i, a in enumerate(alarms) if a["id"] == self.alarm_id)
            alarms[index] = alarm_data

        await interaction.response.send_message(
            embed=discord.Embed(
                title="!알림 등록 완료!",
                description=f"{interaction.user.mention}님이 새로운 알림을 등록했어요! 😍",
                color=discord.Color.green()
            )
        )

# /자기소개
@bot.tree.command(name="자기소개", description="봇의 자기소개를 확인합니다.")
async def introduce(interaction: discord.Interaction):

    embed = discord.Embed(
        title="안녕하세요!",
        description="""
저는 조윤규가 AI를 이용해 만든 봇이에요!

https://ggm.gondr.net/user/profile/441

상업적으로 이용되지 않는, 그저 단순히 알림 역할을 해주는 착한 봇이에요.

`/도움` 명령어를 통해 명령어 및 사용법에 대해 알아보세요!

문의 : nugusaeyo

경기 게임 마이스터 고등학교 6기생 조윤규
"""
    )

    embed.set_image(
        url="https://media.discordapp.net/stickers/1327729351634063462.webp?size=240&quality=lossless"
    )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="도움", description="도움말을 확인합니다.")
async def help_command(interaction: discord.Interaction):

    embed = discord.Embed(
        title="도움말",
        description="사용 가능한 명령어 목록입니다.",
        color=discord.Color.blurple()
    )

    embed.add_field(name="/등록", value="새 알림을 등록합니다.", inline=False)
    embed.add_field(name="/등록현황", value="현재 등록된 알림을 전부 확인합니다.", inline=False)
    embed.add_field(name="/알림채널", value="해당 명령어를 사용한 채팅방에서 알림이 울립니다.", inline=False)
    embed.add_field(name="주의!!", value="멘션 대상이 2인 이상인 경우, 쉼표로 띄어쓰기 없이 추가해주세요!", inline=False)

    await interaction.response.send_message(
        content="# 안녕하세요!\n**도움말**에 오신 것을 환영합니다!",
        embed=embed
    )

# /등록
@bot.tree.command(name="등록", description="새 알림을 등록합니다.")
async def register(interaction: discord.Interaction):

    await interaction.response.send_modal(RegisterModal())

@bot.tree.command(name="등록현황", description="현재 등록된 알림 목록을 확인합니다.")
async def alarm_list(interaction: discord.Interaction):

    if not alarms:
        await interaction.response.send_message("현재 등록된 알림이 없어요!")
        return

    sorted_alarms = sorted(
    alarms,
    key=lambda x: datetime.strptime(
        x["date"] + " " + x["time"],
        "%y/%m/%d %p %I:%M"
    )
)

    max_show = 5
    extra = len(sorted_alarms) - max_show

    embed = discord.Embed(
        title="현재 등록된 알림",
        color=discord.Color.orange()
    )

    views = discord.ui.View()

    for alarm in sorted_alarms[:max_show]:

        embed.add_field(
            name=alarm['title'],
            value=f"{alarm['date']} {alarm['time']}\n{alarm['mentions']}",
            inline=False
        )

        views.add_item(AlarmButton(alarm["id"], alarm["title"]))

    if extra > 0:
        embed.set_footer(text=f"...외 {extra}개")

    await interaction.response.send_message(
        embed=embed,
        view=views
    )


# /알림채널
@bot.tree.command(name="알림채널", description="현재 채널을 알림 채널로 설정합니다.")
async def set_alarm_channel(interaction: discord.Interaction):

    guild_id = interaction.guild.id
    channel_id = interaction.channel.id

    alarm_channels[guild_id] = channel_id

    embed = discord.Embed(
        title="알림 채널 설정 완료",
        description="앞으로 이 채널에서 알림을 보내드릴게요.",
        color=discord.Color.green()
    )

    embed.add_field(
        name="채널",
        value=interaction.channel.mention,
        inline=False
    )

    await interaction.response.send_message(
        embed=embed
    )


@bot.event
async def on_ready():

    await bot.tree.sync()

    if not check_alarm.is_running():
        check_alarm.start()

    print(f"{bot.user} 로그인 성공!")

import os
bot.run(os.environ["DISCORD_TOKEN"])