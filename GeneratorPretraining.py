#!/usr/bin/env python
# coding: utf-8

# In[1]:


import json

import torch
import torch.nn as nn
import torch.nn.functional as F
from architecture import *
from dataset import *


# In[2]:


data_dir = "data-giga/"
train_path = data_dir + "train_seq.json"
valid_path = data_dir + "valid_seq.json"
vocab_path = data_dir + "vocab.json"
lm_path = "trainedELMo/Model5"


# In[3]:


vocab = json.load(open(vocab_path))
VOCAB_SIZE = len(vocab)
INPUT_LEN = 50
OUTPUT_LEN = 50


# In[4]:


training_set = Dataset(train_path, INPUT_LEN, OUTPUT_LEN, vocab[PAD]) #train_seq
validation_set = Dataset(valid_path, INPUT_LEN, OUTPUT_LEN, vocab[PAD])


# In[5]:


batch_size = 50
batch_size_inf = 50
training_generator = Loader(training_set, batch_size=batch_size, shuffle=False)
validation_generator = Loader(validation_set, batch_size=batch_size_inf, shuffle=False)
total_train = int(math.ceil(training_set.size / batch_size))
total_valid = int(math.ceil(validation_set.size / batch_size_inf))


# In[6]:


device = torch.device("cuda")
# unidir = False
# matcher = ContextMatcher(vocab, lm_path, unidir=unidir).to(device)
# matcher.eval()


# In[7]:


# translator = make_translator(
#     VOCAB_SIZE, VOCAB_SIZE, N=4, d_model=256,
#     d_ff=1024, h=8, dropout=0.1, emb_share=True).to(device)
translator = PointerGenerator(
    hidden_dim=256, emb_dim=256, input_len=INPUT_LEN, 
    output_len=OUTPUT_LEN, voc_size=VOCAB_SIZE, eps=1e-9).to(device)
optimizer = torch.optim.RMSprop(translator.parameters(), lr=1e-4)


# In[8]:


start = 1
epochs = 10
n_steps_backprop = 1


# In[ ]:


import wandb

wandb.init(project="contextual-matching-policy-gradient")
wandb.config.update({
    "batch_size": batch_size,
    # "input len":INPUT_LEN,
    # "summary len":OUTPUT_LEN,
    # "unidirection":unidir,
    # "n_steps_backprop":n_steps_backprop,
    })
# wandb.watch([translator, matcher])

vocab_inv = {a:b for b,a in vocab.items()}
def id2sent(ids):
    toks = (vocab_inv[i] for i in ids)
    return " ".join(toks)
def tstring(reward):
    return ", ".join([format(f, ".5g") for f in reward.cpu().numpy()])

# In[ ]:

criterion = nn.CrossEntropyLoss(ignore_index=vocab[PAD], reduction="mean").to(device)

for e in range(start, epochs+1):
    translator.train()
    print("[epoch]", e)
    loss_history = []
    trange = tqdm(training_generator, total=total_train)
    
    losses = []
    for i, (src, tgt) in enumerate(trange):
        bsize, slen = src.shape[:2]
        tgt = src.clone()
        src = src[:,torch.randperm(slen)]
        
        src = src.to(device)
        tgt = tgt.to(device)
        
        src_mask = None#(src != vocab[PAD]).unsqueeze(-2)

        ys, log_p = translator.forward_teacher(
            src=src, src_mask=src_mask, tgt=tgt, max_len=slen, start_symbol=vocab[BOS])
                
        loss = criterion(log_p.view(-1, VOCAB_SIZE), tgt.view(-1))
        # (batch x OUTPUT_LEN)

        ### logging        
        wandb.log({
            "input":id2sent(src[0].cpu().numpy()),
            "output":id2sent(ys[0].cpu().numpy()),
            "target":id2sent(tgt[0].cpu().numpy()),
            "batch loss":loss.item(),
                  })
        ###########
        
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        # losses.append(loss)
        # if len(losses) >= n_steps_backprop:                 
        #     optimizer.zero_grad()
        #     sum(losses).backward()
        #     optimizer.step()
        #     losses = []
    
        loss_history.append(loss.item())
        trange.set_postfix(**{'loss':'{:.5f}'.format(loss.item())})

        if i % 5000 == 4999:
            torch.save(translator.state_dict(), "trained/Pretrain"+str(i))
        
        
    print("Epoch train loss:", np.mean(loss_history))
        
    torch.save(translator.state_dict(), "trained/Pretrain-e"+str(e))
