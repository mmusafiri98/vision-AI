import streamlit as st

user = st.form('my_user')
sentence = user.text_input('Your sentence:', 'username')
say_it = sentence.rstrip('.,!?') + f', {sound}!'
if submit:
    animal.subheader(say_it)
else:
    animal.subheader('&nbsp;')
