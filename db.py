import streamlit as st

animal = st.form('my_animal')



sentence = user.text_input('Your sentence:', 'username')
say_it = sentence.rstrip('.,!?') + f', {sound}!'
if submit:
    animal.subheader(say_it)
else:
    animal.subheader('&nbsp;')
