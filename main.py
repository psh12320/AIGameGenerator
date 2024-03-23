# TODO:
# 1. Get Transcript (DONE)
# 2. Trivia based on Transcript (DONE)
# 3. Use OpenAI to generate quiz questions (DONE)
# 4. Fill-in-the-pronoun or noun, basically grammar check (DONE)
# 5. Put everything into a Telegram bot (DONE)

from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI
import os
import json
from telegram.ext import MessageHandler, CommandHandler, filters, ConversationHandler, ApplicationBuilder, ContextTypes, \
    CallbackQueryHandler, CallbackContext
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove

qns = ''
ans = ''
link = ''
score = 0

OPENAI_API_KEY = 'OPENAI_API_KEY'
os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY
TOKEN = "TOKEN"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
WAITSTATE, FINDLINK, GETQUESTION, GETANSWER, ENDCONVO = range(5)
client = OpenAI()


async def start_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send the YouTube video link here! \n")
    return FINDLINK


async def find_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global link
    if link == '':
        link = update.message.text
        print(link)
    reply_keyboard = [["Trivia", "Grammar"]]
    await update.message.reply_text(
        "Type \'Trivia\' if you would like to test your understanding of the video. \n"
        "Type \'Grammar\' if you would like to test grammar.",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="Trivia or Grammar?"
        ),
    )
    return GETQUESTION

async def wait_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    response = update.message.text



async def get_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global qns
    global ans
    global link
    print("First", qns)
    print(ans)
    reply = update.message.text
    print("Reply is: ", reply)
    if qns == '' and ans == '':
        if reply == "Trivia":
            qns, ans = generate_trivia_qns(get_transcript(link))
            print("Second", qns)
            print(ans)
        elif reply == "Grammar":
            qns, ans = generate_grammar_qns(get_transcript(link))
    print("Before awaiting:", qns)
    await update.message.reply_text(qns[0], reply_markup=ReplyKeyboardRemove())
    return GETANSWER


async def check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global qns
    global ans
    global score
    answer = update.message.text
    curr_qn = qns[0]
    curr_ans = ans[0]
    message = f"Question is {curr_qn}. Model answer is {curr_ans}. The user's answer is {answer}."
    print(message)
    chat_completion = client.chat.completions.create(
        model='gpt-3.5-turbo',  # or 'gpt-3.5-turbo' depending on your preference
        messages=[
            {"role": "system",
             "content": "The following contains 3 items: a question, a model answer, and user's answer. Based on the "
                        "question, if the user's answer is reasonably similar to the model answer, output TRUE, "
                        "otherwise output FALSE. You will only provide a boolean value as your output. In the case "
                        "where the user's answer SOUNDS similar to the model answer, it is best to be lenient and "
                        "marked as correct since the pronunciation might be similar. This especially applies to "
                        "names, such as Devin and Devon. Do check the pronunciations before marking as correct or "
                        "false."},
            {"role": "user", "content": message}
        ]
    )
    bool = chat_completion.choices[0].message.content
    if bool == "TRUE":
        score += 1
        await update.message.reply_text("Your answer is correct! 👏")
    elif bool == "FALSE":
        await update.message.reply_text(f"The correct answer is: {curr_ans}")
    qns = qns[1:]
    ans = ans[1:]
    if qns == [] and ans == []:
        await update.message.reply_text(f"You scored {score} out of 5. Well done and try better in the next quiz! 😊")
        await update.message.reply_text("Click on any button to send a new YouTube link and pick a game! \n"
                                        "Send /cancel if you would like to end this conversation.")
        return ENDCONVO
    else:
        if qns != [] and ans != []:
            await update.message.reply_text(qns[0])
            return GETANSWER
        else:
            return GETQUESTION


def get_transcript(url):
    """
    :param url:
    :return: output
    """
    print(url)
    video_id = url.replace('https://www.youtube.com/watch?v=', '')
    print(video_id)
    transcript = YouTubeTranscriptApi.get_transcript(video_id)
    print(transcript)
    output = ''
    for x in transcript:
        sentence = x['text']
        output += f' {sentence}'
    print(output)
    return output


def generate_trivia_qns(transcript):
    """
    :param transcript:
    :return: trivia game, void
    """
    chat_completion = client.chat.completions.create(
        model='gpt-3.5-turbo',  # or 'gpt-3.5-turbo' depending on your preference
        messages=[
            {"role": "system",
             "content": "The following is the transcript from a Youtube video. You will be designing trivia questions "
                        "for people learning English for the first time based on the transcript. Design 5 trivia "
                        "questions to test whether the viewer of a video has understood the video content. Output the "
                        "questions in the following example format: \"What is the name of the AI Software "
                        "Engineer?\", \"Does the AI Software Engineer have its own command line?\". This is just an "
                        "example. You have to generate questions related to the video content given after this. You "
                        "have to use "
                        "commas in between all questions. and the commas in between the questions. Additionally, "
                        "for every question, also provide the answer. You will output 2 Python lists, one list that "
                        "contains the questions, and one list that contains the answers. There should be no output "
                        "other than the 2 Python lists. An example of the format would be {\"questions\" = [\"What is "
                        "the "
                        "name of the AI Software Engineer?\", \"Does the AI Software Engineer have its own command "
                        "line\"], \"answers\" = [\"Devin\", \"Yes\"]} Include the curly brackets so that my python "
                        "code "
                        "can parse the output. Provide the output such that I can write code later on to convert the "
                        "text into JSON format. The keys, questions and answers, should be in double quotes in the "
                        "output"},
            {"role": "user", "content": transcript}
        ]
    )
    qa = chat_completion.choices[0].message.content
    print(qa)
    json_qa = json.loads(qa)
    questions = json_qa["questions"]
    answers = json_qa["answers"]
    return questions, answers


def generate_grammar_qns(transcript):
    chat_completion = client.chat.completions.create(
        model='gpt-3.5-turbo',  # or 'gpt-3.5-turbo' depending on your preference
        messages=[
            {"role": "system",
             "content": "Based on the following video transcript that will be given to you, you will come up with "
                        "questions that test the grammar of the user. An example of a question would be: \"A sentence "
                        "goes like this: Devin ___ an AI software engineer.  Fill in the dash with a verb. \" "
                        "Another example of a question would be: \" A sentence goes from "
                        "the video goes like this: Do you want to get ___ ice cream? Fill in the dash with an "
                        "article. \". You should come up questions such that strictly only "
                        "test verb tenses, pronouns, and articles. You will design 5 questions and they must test "
                        "more than one type of grammar such as a combination of verbs, pronouns, and articles. The "
                        "transcript may not "
                        "have full proper sentences. In that case, make minimal changes to the sentence but strictly "
                        "ensure that the sentence "
                        "is grammatically correct and only strictly use the grammatically correct sentence for the "
                        "questions. "
                        "Design 5 questions that test grammar. The questions must very strictly follow the exact "
                        "same format as the given examples. "
                        "The question "
                        "should only have one-word answers to ensure "
                        "that only grammar is being tested. None of the answers should be numbers. You will output 2 "
                        "Python lists, "
                        "one list that contains the questions, and one list that contains the answers. There should "
                        "be no output other than the 2 Python lists. An example of the format would be {\"questions\" "
                        "= [\" A sentence goes from the video goes like this: Do you want to get ___ ice cream? Fill "
                        "in the dash with an article. \", \"A sentence goes like this: "
                        "Devin ___ an AI software engineer.  Fill in the dash with a verb. "
                        "\"], \"answers\" = [\"an\", \"is\"]} Include the curly brackets so that my python "
                        "code can parse the output. Provide the output such that I can write code later on to convert "
                        "the text into JSON format. The keys, questions and answers, should be in double quotes in "
                        "the output."},
            {"role": "user", "content": transcript}
        ]
    )
    qa = chat_completion.choices[0].message.content
    print(qa)
    json_qa = json.loads(qa)
    questions = json_qa["questions"]
    answers = json_qa["answers"]
    return questions, answers


async def end_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    response = update.message.text
    if response == "/cancel":
        return ENDCONVO
    else:
        return FINDLINK


async def cancel(update: Update, context: CallbackContext):
    user = update.effective_user
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Conversation has been cancelled. Goodbye, {user.first_name}!",
    )
    return ConversationHandler.END


def main() -> None:
    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start_chat)],
        states={
            WAITSTATE: [MessageHandler(filters.TEXT, wait_state)],
            FINDLINK: [MessageHandler(filters.TEXT, find_link)],
            GETQUESTION: [MessageHandler(filters.TEXT, get_question)],
            GETANSWER: [MessageHandler(filters.TEXT, check_answer)],
            ENDCONVO: [MessageHandler(filters.TEXT, end_conversation)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(conv_handler)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()

