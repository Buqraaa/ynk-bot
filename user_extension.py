# YNK BOT - Kod Uzantisi
# Bu dosyadaki kod bot her basladiginda otomatik calisir.
#
# Kullanmak icin asagidaki ornegi acip kendi kodunu yazabilirsin.
# Hata olursa bot durmaz; panelde ve bot.log dosyasinda hata gorunur.
#
# from discord.ext import commands
#
# class Selam(commands.Cog):
#     def __init__(self, bot):
#         self.bot = bot
#
#     @commands.Cog.listener()
#     async def on_member_join(self, member):
#         kanal = member.guild.system_channel
#         if kanal:
#             await kanal.send(f"Hos geldin {member.mention}!")
#
# async def setup(bot):
#     await bot.add_cog(Selam(bot))
