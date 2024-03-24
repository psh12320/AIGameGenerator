from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI
import os
import json
from telegram.ext import MessageHandler, CommandHandler, filters, ConversationHandler, ApplicationBuilder, ContextTypes, \
    CallbackQueryHandler, CallbackContext
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
TOKEN = os.getenv('TOKEN')
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
FINDLINK, GETQUESTION, GETANSWER = range(3)
client = OpenAI()


async def start_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['qns'] = ''
    context.user_data['ans'] = ''
    context.user_data['link'] = ''
    context.user_data['score'] = 0
    await update.message.reply_text("Send the YouTube video link here! \n"
                                    "The link should follow this format: https://www.youtube.com/watch?v=....\n"
                                    "The YouTube video must have subtitles!")
    return FINDLINK


async def find_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = context.user_data.get('link', '')
    link = update.message.text
    answer = False
    while not answer:
        link = update.message.text
        bool_value = check_if_youtube_link(link)
        if link == "/cancel":
            return ConversationHandler.END
        elif bool_value:
            answer = True
        elif not bool_value:
            await update.message.reply_text("This is not a YouTube video link. \nThe link should follow this format: "
                                            "https://www.youtube.com/watch?v=....\n Try again!")
            return FINDLINK
    context.user_data['link'] = link
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


async def get_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qns = context.user_data.get('qns', '')
    ans = context.user_data.get('ans', '')
    link = context.user_data.get('link', '')
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
    context.user_data['qns'] = qns
    context.user_data['ans'] = ans
    print("Before awaiting:", qns)
    await update.message.reply_text(qns[0], reply_markup=ReplyKeyboardRemove())
    return GETANSWER


async def check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qns = context.user_data.get('qns', '')
    ans = context.user_data.get('ans', '')
    score = context.user_data.get('score', 0)
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
    context.user_data['score'] = score
    context.user_data['qns'] = qns[1:]
    qns = qns[1:]
    context.user_data['ans'] = ans[1:]
    ans = ans[1:]
    if qns == [] and ans == []:
        await update.message.reply_text(f"You scored {score} out of 5. Well done and try better in the next quiz! 😊")
        await update.message.reply_text("Click on /start to send a new YouTube link and pick a game! \n"
                                        "Send /cancel if you would like to end this conversation.")
        return ConversationHandler.END
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


def check_if_youtube_link(link):
    chat_completion = client.chat.completions.create(
        model='gpt-3.5-turbo',  # or 'gpt-3.5-turbo' depending on your preference
        messages=[
            {"role": "system",
             "content": "You are given the following content. Check if it is a YouTube video link carefully and "
                        "output either True or False."},
            {"role": "user", "content": link}
        ]
    )
    answer = chat_completion.choices[0].message.content
    if answer == "True":
        return True
    else:
        return False


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


# async def end_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
#    response = update.message.text
#    if response == "/cancel":
#        return ConversationHandler.END
#    else:
#        return WAITSTATE


async def wait_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    response = update.message.text
    if response != "/cancel":
        await update.message.reply_text("I'm not sure what you mean. \nClick /start to try a new game!")


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
            FINDLINK: [MessageHandler(filters.TEXT, find_link)],
            GETQUESTION: [MessageHandler(filters.TEXT, get_question)],
            GETANSWER: [MessageHandler(filters.TEXT, check_answer)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.ALL, wait_state))
    application.run_polling(allowed_updates=Update.ALL_TYPES)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()
