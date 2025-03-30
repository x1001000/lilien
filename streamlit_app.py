import streamlit as st
from openai import OpenAI
import requests
import json
import os
from datetime import datetime, timezone, timedelta
tz = timezone(timedelta(hours=+8))

# Create session state variables
if 'client' not in st.session_state:
    st.session_state.client = OpenAI()
    st.session_state.messages = []
    r = requests.get(os.getenv('MEMORY_API'))
    for row in r.json()['data']:
        st.session_state.messages.append({"role": "system", "content": row['timestamp']})
        st.session_state.messages.append({"role": "user", "content": row['userMessage']})
        st.session_state.messages.append({"role": "assistant", "content": row['assistantMessage']})
    st.session_state.system = {}
    for line in requests.get(os.getenv('SYSTEM_PROMPT_URL')).text.split('\n'):
        if '更新日期'  in line:
            st.session_state.system[line] = ''
        else:
            st.session_state.system[list(st.session_state.system.keys())[-1]] += line + '\n'
    st.session_state.matters = []
    r = requests.get(os.getenv('MEMORY_API')+'?sheet=LTM')
    for row in r.json()['data']:
        st.session_state.matters.append(row[0])

tools = [
    {
        'type': 'function',
        'function': {
            'name': 'add_note',
            'description': "Call this function when the user's message relates to the following matters:\n{}".format('\n'.join(st.session_state.matters)),
            'parameters': {
                'type': 'object',
                'properties': {
                    'relevant matters': {
                        'type': 'string',
                    },
                },
                'required': ['relevant matters'],
            },
        }
    },
]

st.title('🧚‍♀️ Lilien')

col1, col2 = st.columns(2)
with col1:
    version = st.selectbox("系統提示", list(st.session_state.system.keys()))
with col2:
    model = st.selectbox("語言模型", ['gpt-4o-mini', 'gpt-4o', 'o3-mini'])

system_prompt = st.session_state.system[version]
print(system_prompt)
print(tools[0]['function']['description'])

# Display the existing chat messages via `st.chat_message`.
for message in st.session_state.messages:
    if message["role"] == "system":
        current_time = message["content"]
        st.html(f'<p align="right">{current_time[2:-6].replace("-", "/").replace("T", " ")}</p>')
        continue
    with st.chat_message(message["role"], avatar=None if message["role"] == "user" else '🧚‍♀️'):
        st.markdown(message["content"])

# Create a chat input field to allow the user to enter a message. This will display
# automatically at the bottom of the page.
if user_prompt := st.chat_input("你說 我聽"):

    # Store and display the current_time
    current_time = datetime.now(tz).replace(microsecond=0).isoformat()
    st.session_state.messages.append({"role": "system", "content": current_time})
    st.html(f'<p align="right">{current_time[2:-6].replace("-", "/").replace("T", " ")}</p>')
    # Store and display the current user_prompt.
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    response = st.session_state.client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": user_prompt}],
        tools=tools,
    )
    print(response.choices[0].message.content)
    tool_calls = response.choices[0].message.tool_calls
    if tool_calls:
        for tool_call in tool_calls:
            print(tool_call.function.name)
            print(tool_call.function.arguments)
            relevant_matters = json.loads(tool_call.function.arguments)['relevant matters']
    else:
        relevant_matters = ''
    # Generate a response using the OpenAI API.
    stream = st.session_state.client.chat.completions.create(
        model=model,
        messages=[
            {'role': 'system', 'content': system_prompt},
            ] + st.session_state.messages,
        stream=True,
    )

    # Stream the response to the chat using `st.write_stream`, then store it in 
    # session state.
    with st.chat_message("assistant", avatar='🧚‍♀️'):
        response = st.write_stream(stream)
    st.session_state.messages.append({"role": "assistant", "content": response})
    payload = {
        "timestamp": current_time,
        "userMessage": user_prompt,
        "assistantMessage": response,
        "relevantMatters": relevant_matters,
        }
    requests.post(os.getenv('MEMORY_API'), json=payload)
