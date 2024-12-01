# Testagon

Testagon is a python package that leverages the capabilities of LLMs to reason about logic invariants in your python programs and uses them to generate a suite of comprehensive unit tests. 

Testagon understands your project layout and will accurately find the python files that need to be tested. It will also generate a tests/ folder if it is not present. 

Testagon follows the Actor-Critic method, creating a feedback loop that finds logic vulnerabilities in your source code. 

The “Actor”:
- Detects invariants and writes them into the docstring of your program files
- Generates a test directory and writes unit tests for each one of your program files, allowing the invariants to guide the process

The “Critic”:
- Evaluates your program on the unit tests and records the response
- Sends the response back to the “Actor” to restart the process, aiming to refine the tests and invariants

# Installation

Installing Testagon is easy, just run `pip install testagon`

We support python >= 3.9

# How to Use

- `testagon init` in your project directory
- `testagon generate` to generate unit tests using the actor-critic method
- `testagon test` to evaluate your program on the unit tests

# References
<a id="1">[1]</a>
Pei, Kexin, David Bieber, Kensen Shi, Charles Sutton, and Pengcheng Yin. "Can large language models reason about program invariants?." In International Conference on Machine Learning, pp. 27496-27520. PMLR, 2023. https://dl.acm.org/doi/10.5555/3618408.3619552

<a id="2">[2]</a>
Kalyanpur, Aditya, Kailash Karthik Saravanakumar, Victor Barres, Jennifer Chu-Carroll, David Melville, and David Ferrucci. "Llm-arc: Enhancing llms with an automated reasoning critic." arXiv preprint arXiv:2406.17663 (2024). https://arxiv.org/pdf/2406.17663v2

<a id="3">[3]</a> 
He, W., 2019. Invariant Detection with Program Verification Tools. arXiv preprint arXiv:1906.11929. https://arxiv.org/pdf/1906.11929

<a id="4">[4]</a> 
Schäfer, Max, Sarah Nadi, Aryaz Eghbali, and Frank Tip. "An empirical evaluation of using large language models for automated unit test generation." IEEE Transactions on Software Engineering (2023). https://arxiv.org/pdf/2302.06527

<a id="5">[5]</a> 
Chen, Yinghao, Zehao Hu, Chen Zhi, Junxiao Han, Shuiguang Deng, and Jianwei Yin. "Chatunitest: A framework for llm-based test generation." In Companion Proceedings of the 32nd ACM International Conference on the Foundations of Software Engineering, pp. 572-576. 2024. https://dl.acm.org/doi/abs/10.1145/3663529.3663801

<a id="6">[6]</a> 
Nong, Yu, Haoran Yang, Long Cheng, Hongxin Hu, and Haipeng Cai. "Automated Software Vulnerability Patching using Large Language Models." arXiv preprint arXiv:2408.13597 (2024). https://arxiv.org/abs/2408.13597

<a id="7">[7]</a> 
Lemieux, Caroline, Jeevana Priya Inala, Shuvendu K. Lahiri, and Siddhartha Sen. "Codamosa: Escaping coverage plateaus in test generation with pre-trained large language models." In 2023 IEEE/ACM 45th International Conference on Software Engineering (ICSE), pp. 919-931. IEEE, 2023. https://www.carolemieux.com/codamosa_icse23.pdf

# Misc
- Model used: GPT-4o with structured JSON output support
- Team members: Amey Walimbe, Anshuman Dash, Carson Kopper, Tim Kim
